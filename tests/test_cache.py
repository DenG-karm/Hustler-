"""YouTubeCache: gerçek SQLite (tmp_path) üzerinde TTL ve UPSERT davranışı."""

import time

import pytest

from services.core.hustler.db import Database
from services.core.hustler.storage.cache import YouTubeCache


async def _age(db: Database, key: str, seconds: float) -> None:
    await db.execute_write(
        "UPDATE youtube_cache SET created_at = created_at - ? WHERE cache_key = ?",
        (seconds, key),
    )
    await db.trigger_maintenance()


async def test_miss_returns_none(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()

    assert await cache.get("nope") is None


async def test_set_then_get_round_trips_exact_payload(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()
    payload: dict[str, object] = {"items": [{"id": "a", "ünicode": "ğüş"}], "n": 3}

    await cache.set("k", payload)
    await db.trigger_maintenance()

    assert await cache.get("k") == payload


async def test_upsert_overwrites_value_for_same_key(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()

    await cache.set("k", {"v": 1})
    await cache.set("k", {"v": 2})
    await db.trigger_maintenance()

    assert await cache.get("k") == {"v": 2}
    conn = await db.get_reader()
    async with conn.execute("SELECT COUNT(*) FROM youtube_cache") as cur:
        row = await cur.fetchone()
    await conn.close()
    assert row is not None and row[0] == 1


async def test_expired_entry_is_treated_as_miss(db: Database) -> None:
    cache = YouTubeCache(db, ttl_seconds=60)
    await cache.init_tables()
    await cache.set("k", {"v": 1})
    await db.trigger_maintenance()

    await _age(db, "k", 120)

    assert await cache.get("k") is None


async def test_entry_within_ttl_is_still_served(db: Database) -> None:
    cache = YouTubeCache(db, ttl_seconds=60)
    await cache.init_tables()
    await cache.set("k", {"v": 1})
    await db.trigger_maintenance()

    await _age(db, "k", 30)

    assert await cache.get("k") == {"v": 1}


async def test_non_dict_json_in_cache_is_ignored(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()
    await db.execute_write(
        "INSERT INTO youtube_cache VALUES (?, ?, ?)", ("k", "[1, 2]", time.time())
    )
    await db.trigger_maintenance()

    assert await cache.get("k") is None


@pytest.mark.parametrize("bad_json", ["{broken", "", "nul"])
async def test_corrupt_json_does_not_crash_and_returns_none(
    db: Database, bad_json: str
) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()
    await db.execute_write(
        "INSERT INTO youtube_cache VALUES (?, ?, ?)", ("k", bad_json, time.time())
    )
    await db.trigger_maintenance()

    assert await cache.get("k") is None


async def test_get_before_init_tables_swallows_error(db: Database) -> None:
    assert await YouTubeCache(db).get("k") is None


async def test_set_non_serializable_raises_type_error(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()

    with pytest.raises(TypeError):
        await cache.set("k", {"x": object()})
