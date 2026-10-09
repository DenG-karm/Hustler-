"""K-008: WAL + tek yazıcı kuyruğu altında eşzamanlı okuma/yazma stresi."""

import asyncio
import time
from pathlib import Path

import aiosqlite
import pytest

from services.core.hustler.db import Database

WRITERS = 10
READERS = 10


async def _count(db: Database) -> int:
    reader = await db.get_reader()
    try:
        async with reader.execute("SELECT COUNT(*) FROM stress") as cur:
            row = await cur.fetchone()
    finally:
        await reader.close()
    assert row is not None
    return int(row[0])


@pytest.fixture
async def stress_db(db: Database) -> Database:
    await db.execute_write(
        "CREATE TABLE stress (id INTEGER PRIMARY KEY, worker INTEGER, n INTEGER)"
    )
    return db


async def test_ten_concurrent_tasks_read_and_write_without_database_is_locked(
    stress_db: Database,
) -> None:
    per_writer = 20

    async def writer(worker: int) -> None:
        for n in range(per_writer):
            await stress_db.execute_write(
                "INSERT INTO stress (worker, n) VALUES (?, ?)", (worker, n)
            )

    async def reader() -> int:
        last = 0
        for _ in range(per_writer):
            last = await _count(stress_db)
            await asyncio.sleep(0)
        return last

    start = time.perf_counter()
    results = await asyncio.wait_for(
        asyncio.gather(
            *[writer(w) for w in range(WRITERS)],
            *[reader() for _ in range(READERS)],
            return_exceptions=True,
        ),
        timeout=30,
    )
    elapsed = time.perf_counter() - start

    errors = [r for r in results if isinstance(r, BaseException)]
    assert errors == []  # özellikle: "database is locked" yok
    assert await _count(stress_db) == WRITERS * per_writer
    assert elapsed < 20.0


async def test_concurrent_readers_see_monotonic_row_counts_while_writing(
    stress_db: Database,
) -> None:
    total = 50

    async def writer() -> None:
        for n in range(total):
            await stress_db.execute_write(
                "INSERT INTO stress (worker, n) VALUES (0, ?)", (n,)
            )

    async def reader() -> list[int]:
        seen: list[int] = []
        for _ in range(total):
            seen.append(await _count(stress_db))
            await asyncio.sleep(0)
        return seen

    _, *series = await asyncio.wait_for(
        asyncio.gather(writer(), *[reader() for _ in range(5)]), timeout=30
    )

    for seen in series:
        assert isinstance(seen, list)
        assert seen == sorted(seen)
        assert 0 <= seen[-1] <= total


async def test_every_connection_uses_wal_journal_mode(stress_db: Database) -> None:
    reader = await stress_db.get_reader()
    try:
        async with reader.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
    finally:
        await reader.close()

    assert row is not None
    assert str(row[0]).lower() == "wal"


async def test_writer_queue_surfaces_sql_error_and_keeps_serving(
    stress_db: Database,
) -> None:
    with pytest.raises(aiosqlite.OperationalError):
        await stress_db.execute_write("INSERT INTO no_such_table VALUES (1)")

    await stress_db.execute_write("INSERT INTO stress (worker, n) VALUES (1, 1)")

    assert await _count(stress_db) == 1


async def test_maintenance_job_runs_through_queue_without_error(
    stress_db: Database,
) -> None:
    await stress_db.execute_write("INSERT INTO stress (worker, n) VALUES (1, 1)")
    await stress_db.execute_write("DELETE FROM stress")

    await asyncio.wait_for(stress_db.trigger_maintenance(), timeout=5)

    assert await _count(stress_db) == 0


async def test_close_without_init_is_a_noop(tmp_path: Path) -> None:
    database = Database(tmp_path / "never_opened.db")

    await database.close()

    assert not (tmp_path / "never_opened.db").exists()
