"""Scheduler döngüleri: hata izolasyonu ve iptal davranışı (gerçek YouTube yok)."""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

from services.core.hustler.db import Database
from services.core.hustler.services.discovery import DiscoveryOrchestrator
from services.core.hustler.tasks.scheduler import discovery_loop, maintenance_loop


class FlakyOrchestrator:
    """İlk çağrıda patlar, sonrakilerde başarılı olur."""

    def __init__(self) -> None:
        self.call_count = 0

    async def run_discovery(
        self, topic: str, max_results: int = 50, score_threshold: float = 30.0
    ) -> dict[str, str]:
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("YouTube API 500")
        return {"status": "success"}


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(tmp_path / "scheduler.db")
    await database.init()
    await database.execute_write(
        "CREATE TABLE IF NOT EXISTS youtube_cache "
        "(cache_key TEXT PRIMARY KEY, response_json TEXT, created_at REAL)"
    )
    yield database
    await database.close()


async def _cancel(task: "asyncio.Task[None]") -> None:
    task.cancel()
    await asyncio.wait_for(task, timeout=2)


async def test_discovery_loop_survives_failure_and_keeps_running() -> None:
    orch = FlakyOrchestrator()
    task = asyncio.create_task(
        discovery_loop(
            cast(DiscoveryOrchestrator, orch), "topic", interval_sec=cast(int, 0.05)
        )
    )

    deadline = time.perf_counter() + 2.0
    while orch.call_count < 3 and time.perf_counter() < deadline:
        await asyncio.sleep(0.01)
    still_running = not task.done()
    await _cancel(task)

    assert orch.call_count >= 3  # 1. çağrı patladı, döngü yaşadı
    assert still_running is True
    assert task.done() and not task.cancelled()  # CancelledError yutuldu, temiz çıkış


async def test_discovery_loop_stops_cleanly_on_cancel_before_first_tick() -> None:
    orch = FlakyOrchestrator()
    task = asyncio.create_task(
        discovery_loop(cast(DiscoveryOrchestrator, orch), "t", interval_sec=60)
    )
    await asyncio.sleep(0)

    await _cancel(task)

    assert orch.call_count == 0
    assert task.done()


async def test_maintenance_loop_prunes_only_expired_cache_rows(db: Database) -> None:
    now = time.time()
    await db.execute_write(
        "INSERT INTO youtube_cache VALUES ('old', '{}', ?)", (now - 10_000,)
    )
    await db.execute_write(
        "INSERT INTO youtube_cache VALUES ('fresh', '{}', ?)", (now,)
    )
    task = asyncio.create_task(
        maintenance_loop(db, cache_ttl_sec=3600, interval_sec=cast(int, 0.05))
    )

    await asyncio.sleep(0.4)
    await _cancel(task)

    reader = await db.get_reader()
    try:
        async with reader.execute("SELECT cache_key FROM youtube_cache") as cur:
            keys = [row[0] for row in await cur.fetchall()]
    finally:
        await reader.close()
    assert keys == ["fresh"]


async def test_maintenance_loop_survives_missing_table(tmp_path: Path) -> None:
    database = Database(tmp_path / "no_table.db")
    await database.init()
    task = asyncio.create_task(
        maintenance_loop(database, cache_ttl_sec=1, interval_sec=cast(int, 0.05))
    )
    try:
        await asyncio.sleep(0.3)
        still_running = not task.done()
    finally:
        await _cancel(task)
        await database.close()

    assert still_running is True
