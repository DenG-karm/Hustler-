"""
K-008 & K-802: SQLite WAL ve Tek Yazıcı Kuyruğu (WriterQueue)
- Tek yazıcı asenkron kuyruk üzerinden çalışır (veritabanı kilidini sıfıra indirir).
- Okuyucular bağımsızdır (WAL modu).
- auto_vacuum=INCREMENTAL ve bakım tetikleyicisi.
"""

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import structlog

log = structlog.get_logger()


@dataclass
class WriteJob:
    query: str
    params: tuple[object, ...] = ()
    many_params: Optional[Sequence[tuple[object, ...]]] = None
    is_maintenance: bool = False
    result_fut: Optional[asyncio.Future[None]] = None


class PooledReaderConnection:
    """
    Okuyucu bağlantısını sarmalar; close() çağrıldığında bağlantıyı kapatmak yerine
    Database._reader_pool havuzuna iade eder (Zero-Thread-Churn).
    """

    def __init__(self, conn: aiosqlite.Connection, db: "Database") -> None:
        self._conn = conn
        self._db = db
        self._returned = False

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> Any:
        if self._returned:
            raise ValueError("Connection closed")
        return self._conn.execute(sql, parameters)

    def executemany(self, sql: str, parameters: Iterable[Iterable[Any]]) -> Any:
        if self._returned:
            raise ValueError("Connection closed")
        return self._conn.executemany(sql, parameters)

    @property
    def row_factory(self) -> Any:
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, factory: Any) -> None:
        self._conn.row_factory = factory

    async def close(self) -> None:
        if self._returned:
            return
        self._returned = True
        try:
            try:
                await self._conn.rollback()
                self._conn.row_factory = None
            except Exception:
                await self._db._discard_reader(self._conn)
                return
            await self._db._release_reader(self._conn)
        finally:
            self._db._reader_sem.release()

    async def __aenter__(self) -> "PooledReaderConnection":
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.close()


class Database:
    def __init__(self, db_path: Path, reader_pool_size: int = 4):
        self.db_path = db_path
        self.reader_pool_size = max(1, reader_pool_size)
        self._write_queue: asyncio.Queue[WriteJob | None] = asyncio.Queue()
        self._reader_pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=self.reader_pool_size)
        self._reader_sem: asyncio.Semaphore = asyncio.Semaphore(self.reader_pool_size)
        self._all_reader_conns: set[aiosqlite.Connection] = set()
        self._writer_task: Optional[asyncio.Task[None]] = None
        self._writer_conn: Optional[aiosqlite.Connection] = None
        self._closed: bool = False

    @property
    def path(self) -> Path:
        return self.db_path

    async def init(self) -> None:
        self._closed = False
        self._reader_sem = asyncio.Semaphore(self.reader_pool_size)
        # Veritabanı oluşturulurken (dışarıdan lock almadan) kalıcı ayarlar
        init_conn = aiosqlite.connect(self.db_path)
        init_conn.daemon = True
        async with init_conn as conn:
            await conn.execute("PRAGMA auto_vacuum=INCREMENTAL;")
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            await conn.execute("PRAGMA busy_timeout=5000;")

        self._writer_task = asyncio.create_task(self._writer_loop())

    async def _discard_reader(self, conn: aiosqlite.Connection) -> None:
        self._all_reader_conns.discard(conn)
        try:
            await conn.close()
        except Exception as e:
            log.warning("reader_conn_close_error", error=str(e))

    async def _drain_reader_pool(self) -> None:
        """Havuzdaki boşta bekleyen okuyucu bağlantılarını fiziksel olarak kapatır (WAL TRUNCATE kilidini önler)."""
        while not self._reader_pool.empty():
            try:
                conn = self._reader_pool.get_nowait()
                await self._discard_reader(conn)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                log.warning("reader_pool_close_error", error=str(e))

    async def _release_reader(self, conn: aiosqlite.Connection) -> None:
        if self._closed:
            await self._discard_reader(conn)
            return
        try:
            self._reader_pool.put_nowait(conn)
        except asyncio.QueueFull:
            await self._discard_reader(conn)

    async def close(self) -> None:
        self._closed = True
        await self._drain_reader_pool()
        for conn in list(self._all_reader_conns):
            await self._discard_reader(conn)
        if self._writer_task:
            await self._write_queue.put(None)
            await self._writer_task
        await self._drain_reader_pool()

    async def get_reader(self) -> PooledReaderConnection:
        """
        Sabit boyutlu (Bounded) ReaderPool üzerinden bağlantı üretici.
        Semaphore ile toplam eşzamanlı okuyucu bağlantısı sayısı asla reader_pool_size sınırını aşmaz.
        """
        if self._closed:
            raise RuntimeError("Database is closed")

        await self._reader_sem.acquire()
        if self._closed:
            self._reader_sem.release()
            raise RuntimeError("Database is closed")

        try:
            while not self._reader_pool.empty():
                try:
                    conn = self._reader_pool.get_nowait()
                    return PooledReaderConnection(conn, self)
                except asyncio.QueueEmpty:
                    break

            raw_conn = aiosqlite.connect(self.db_path)
            raw_conn.daemon = True
            conn = await raw_conn
            self._all_reader_conns.add(conn)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            await conn.execute("PRAGMA busy_timeout=5000;")
            return PooledReaderConnection(conn, self)
        except Exception:
            self._reader_sem.release()
            raise

    async def execute_write(self, query: str, params: tuple[object, ...] = ()) -> None:
        """Sistemin hiçbir yerinden doğrudan yazma yapılmaz, istek kuyruğa eklenir."""
        if self._closed:
            raise RuntimeError("Database is closed")
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        await self._write_queue.put(WriteJob(query=query, params=params, result_fut=fut))
        await fut

    async def executemany_write(
        self, query: str, params_seq: Sequence[tuple[object, ...]]
    ) -> None:
        """Toplu yazma işlemlerini tek bir atomik transaction (commit) içinde yürütür."""
        if self._closed:
            raise RuntimeError("Database is closed")
        params_list = list(params_seq)
        if not params_list:
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        await self._write_queue.put(
            WriteJob(query=query, many_params=params_list, result_fut=fut)
        )
        await fut

    async def trigger_maintenance(self) -> None:
        """Bakım işi türüyle incremental_vacuum tetikleyicisi."""
        if self._closed:
            raise RuntimeError("Database is closed")
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        await self._write_queue.put(WriteJob(query="", is_maintenance=True, result_fut=fut))
        await fut

    async def checkpoint_truncate(self) -> None:
        """Kapanış veya bakım öncesi WAL dosyasını ana DB'ye aktarıp TRUNCATE eder."""
        await self._drain_reader_pool()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        await self._write_queue.put(WriteJob(query="PRAGMA wal_checkpoint(TRUNCATE);", result_fut=fut))
        await fut

    async def _writer_loop(self) -> None:
        raw_writer = aiosqlite.connect(self.db_path)
        raw_writer.daemon = True
        self._writer_conn = await raw_writer
        await self._writer_conn.execute("PRAGMA journal_mode=WAL;")
        await self._writer_conn.execute("PRAGMA synchronous=NORMAL;")
        await self._writer_conn.execute("PRAGMA foreign_keys=ON;")
        await self._writer_conn.execute("PRAGMA busy_timeout=5000;")

        log.info("writer_queue_started")
        while True:
            job = await self._write_queue.get()
            if job is None:
                self._write_queue.task_done()
                break

            try:
                if job.is_maintenance:
                    # auto_vacuum=INCREMENTAL ile biriken freelist sayfalarını OS'e iade et
                    await self._writer_conn.execute("PRAGMA incremental_vacuum;")
                elif job.many_params is not None:
                    await self._writer_conn.executemany(job.query, job.many_params)
                    await self._writer_conn.commit()
                else:
                    await self._writer_conn.execute(job.query, job.params)
                    await self._writer_conn.commit()

                if job.result_fut and not job.result_fut.done():
                    job.result_fut.set_result(None)
            except Exception as e:
                log.error("write_job_failed", error=str(e), query=job.query)
                if job.result_fut and not job.result_fut.done():
                    job.result_fut.set_exception(e)
            finally:
                self._write_queue.task_done()

        try:
            await self._writer_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception as e:
            log.warning("wal_checkpoint_failed", error=str(e))

        await self._writer_conn.close()
        log.info("writer_queue_stopped")
