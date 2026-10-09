"""DiscoveryOrchestrator: gerçek skorlama + gerçek SQLite; yalnızca YouTube HTTP sahte."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from tenacity import wait_none

from services.core.hustler.adapters import youtube
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.db import Database
from services.core.hustler.services.discovery import DiscoveryOrchestrator


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(youtube, "wait_random_exponential", lambda **_: wait_none())


def _iso(hours_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _video(
    vid: str, hours: float, views: int, likes: int, comments: int
) -> dict[str, object]:
    return {
        "id": vid,
        "snippet": {"title": f"T-{vid}", "publishedAt": _iso(hours)},
        "statistics": {
            "viewCount": str(views),
            "likeCount": str(likes),
            "commentCount": str(comments),
        },
    }


def _client(
    search_items: Sequence[Mapping[str, object]], videos: Sequence[Mapping[str, object]]
) -> YouTubeClient:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": list(search_items)})
        return httpx.Response(200, json={"items": list(videos)})

    client = YouTubeClient("K")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def _rows(db: Database) -> list[tuple[str, str, str, float]]:
    await db.trigger_maintenance()
    conn = await db.get_reader()
    async with conn.execute(
        "SELECT video_id, title, topic, score FROM discovery_videos ORDER BY video_id"
    ) as cur:
        rows = [(r[0], r[1], r[2], r[3]) for r in await cur.fetchall()]
    await conn.close()
    return rows


async def test_winners_are_persisted_and_losers_discarded(db: Database) -> None:
    search = [{"id": {"videoId": "hot"}}, {"id": {"videoId": "cold"}}]
    videos = [_video("hot", 2, 100_000, 15_000, 500), _video("cold", 2000, 10, 0, 0)]
    client = _client(search, videos)
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    result = await orch.run_discovery("kedi", score_threshold=30.0)

    assert result["fetched"] == 2
    assert result["inserted"] == 1
    assert result["discarded"] == 1
    assert result["max_score"] >= 30.0
    rows = await _rows(db)
    assert [(r[0], r[1], r[2]) for r in rows] == [("hot", "T-hot", "kedi")]
    assert rows[0][3] == pytest.approx(result["max_score"])
    await client._client.aclose()  # type: ignore[union-attr]


async def test_no_search_results_returns_zeros_and_skips_details(db: Database) -> None:
    client = _client([], [])
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    result = await orch.run_discovery("x")

    assert result == {"fetched": 0, "discarded": 0, "inserted": 0, "max_score": 0.0}
    assert client.quota_used == 100
    await client._client.aclose()  # type: ignore[union-attr]


async def test_search_items_without_video_id_are_skipped(db: Database) -> None:
    client = _client(
        [{"id": {"channelId": "c"}}, {"id": {"videoId": "a"}}],
        [_video("a", 1, 50_000, 5_000, 100)],
    )
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    result = await orch.run_discovery("x", score_threshold=0.0)

    assert result["fetched"] == 1
    assert [r[0] for r in await _rows(db)] == ["a"]
    await client._client.aclose()  # type: ignore[union-attr]


async def test_rediscovery_upserts_instead_of_duplicating(db: Database) -> None:
    client = _client([{"id": {"videoId": "a"}}], [_video("a", 1, 50_000, 5_000, 100)])
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    await orch.run_discovery("x", score_threshold=0.0)
    await orch.run_discovery("x", score_threshold=0.0)

    assert len(await _rows(db)) == 1
    await client._client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "stats",
    [{}, {"viewCount": "0", "likeCount": "0", "commentCount": "0"}],
)
async def test_zero_or_missing_stats_never_crash_and_score_below_threshold(
    db: Database, stats: dict[str, str]
) -> None:
    video = {"id": "a", "snippet": {"publishedAt": _iso(1)}, "statistics": stats}
    client = _client([{"id": {"videoId": "a"}}], [video])
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    result = await orch.run_discovery("x", score_threshold=1.0)

    assert result["inserted"] == 0 and result["discarded"] == 1
    await client._client.aclose()  # type: ignore[union-attr]


async def test_invalid_published_date_scores_zero_and_is_discarded(
    db: Database,
) -> None:
    video = _video("a", 1, 10**6, 10**5, 10**3)
    video["snippet"] = {"title": "t", "publishedAt": "bozuk-tarih"}
    client = _client([{"id": {"videoId": "a"}}], [video])
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    result = await orch.run_discovery("x", score_threshold=1.0)

    assert result["discarded"] == 1 and result["max_score"] == 0.0
    await client._client.aclose()  # type: ignore[union-attr]


async def test_non_numeric_view_count_raises_value_error(db: Database) -> None:
    video = _video("a", 1, 1, 1, 1)
    video["statistics"] = {"viewCount": "çok"}
    client = _client([{"id": {"videoId": "a"}}], [video])
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    with pytest.raises(ValueError):
        await orch.run_discovery("x")
    await client._client.aclose()  # type: ignore[union-attr]


async def test_api_failure_propagates_and_writes_nothing(db: Database) -> None:
    client = YouTubeClient("K")
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500, json={}))
    )
    orch = DiscoveryOrchestrator(client, db)
    await orch.init_tables()

    with pytest.raises(httpx.HTTPStatusError):
        await orch.run_discovery("x")

    assert await _rows(db) == []
    await client._client.aclose()
