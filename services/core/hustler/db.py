"""
K-008: SQLite WAL ve Tek Yazıcı Kuyruğu (WriterQueue)
- Tek yazıcı asenkron kuyruk üzerinden çalışır (veritabanı kilidini sıfıra indirir).
- Okuyucular bağımsızdır.
- auto_vacuum=INCREMENTAL ve bakım tetikleyicisi.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import structlog

log = structlog.get_logger()

@dataclass
class WriteJob:
    query: str
    params: tuple = ()
    is_maintenance: bool = False
    result_fut: Optional[asyncio.Future[Any]] = None

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._write_queue: asyncio.Queue[WriteJob | None] = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task[Any]] = None
        self._writer_conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        # Veritabanı oluşturulurken (dışarıdan lock almadan) kalıcı ayarlar
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA auto_vacuum=INCREMENTAL;")
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA busy_timeout=5000;")
        
        self._writer_task = asyncio.create_task(self._writer_loop())

    async def close(self) -> None:
        if self._writer_task:
            await self._write_queue.put(None)
            await self._writer_task

    async def get_reader(self) -> aiosqlite.Connection:
        """
        Okuyucu havuzu için bağlantı üretici.
        Okuyucular bağımsız çalışır ve yazıcıları beklemez (WAL sayesinde).
        """
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    async def execute_write(self, query: str, params: tuple = ()) -> None:
        """Sistemin hiçbir yerinden doğrudan yazma yapılmaz, istek kuyruğa eklenir."""
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._write_queue.put(WriteJob(query=query, params=params, result_fut=fut))
        await fut

    async def trigger_maintenance(self) -> None:
        """Bakım işi türüyle incremental_vacuum tetikleyicisi."""
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._write_queue.put(WriteJob(query="", is_maintenance=True, result_fut=fut))
        await fut

    async def _writer_loop(self) -> None:
        self._writer_conn = await aiosqlite.connect(self.db_path)
        await self._writer_conn.execute("PRAGMA journal_mode=WAL;")
        await self._writer_conn.execute("PRAGMA synchronous=NORMAL;")
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
                
        await self._writer_conn.close()
        log.info("writer_queue_stopped")
