"""YouTubeClient: gerçek istemci mantığı; yalnızca HTTP taşıması (MockTransport) sahte."""

from collections.abc import Callable

import httpx
import pytest
from tenacity import wait_none

from services.core.hustler.adapters import youtube
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.db import Database
from services.core.hustler.storage.cache import YouTubeCache

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(youtube, "wait_random_exponential", lambda **_: wait_none())


def _client(handler: Handler, cache: YouTubeCache | None = None) -> YouTubeClient:
    client = YouTubeClient("KEY", cache)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def _page(n: int, token: str | None = None, start: int = 0) -> dict[str, object]:
    page: dict[str, object] = {
        "items": [{"id": {"videoId": f"v{start + i}"}} for i in range(n)]
    }
    if token:
        page["nextPageToken"] = token
    return page


async def test_search_paginates_and_sends_key_and_params() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if "pageToken" in req.url.params:
            return httpx.Response(200, json=_page(2, None, 3))
        return httpx.Response(200, json=_page(3, "T2"))

    client = _client(handler)
    items = [i async for i in client.search_shorts("kedi", max_results=5)]

    assert [i["id"]["videoId"] for i in items] == ["v0", "v1", "v2", "v3", "v4"]
    assert len(seen) == 2
    assert seen[0].url.params["key"] == "KEY"
    assert seen[0].url.params["q"] == "kedi"
    assert seen[0].url.params["maxResults"] == "5"
    assert seen[1].url.params["pageToken"] == "T2"
    assert seen[1].url.params["maxResults"] == "2"
    assert client.quota_used == 200
    await client._client.aclose()  # type: ignore[union-attr]


async def test_max_results_is_capped_at_50_per_request() -> None:
    sizes: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sizes.append(req.url.params["maxResults"])
        return httpx.Response(200, json=_page(50, "n"))

    client = _client(handler)
    items = [i async for i in client.search_shorts("x", max_results=60)]

    assert len(items) == 60
    assert sizes == ["50", "10"]
    await client._client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "payload", [{"items": []}, {}, {"items": [], "nextPageToken": "t"}]
)
async def test_empty_search_terminates_without_looping(
    payload: dict[str, object],
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    client = _client(handler)

    assert [i async for i in client.search_shorts("x")] == []
    assert calls == 1
    await client._client.aclose()  # type: ignore[union-attr]


async def test_videos_are_batched_by_50_and_cost_one_quota_each() -> None:
    batches: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        ids = req.url.params["id"].split(",")
        batches.append(len(ids))
        return httpx.Response(200, json={"items": [{"id": i} for i in ids]})

    client = _client(handler)
    result = await client.get_videos_details([f"v{i}" for i in range(120)])

    assert batches == [50, 50, 20]
    assert len(result) == 120
    assert client.quota_used == 3
    await client._client.aclose()  # type: ignore[union-attr]


async def test_no_video_ids_makes_no_request() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("istek atılmamalıydı")

    client = _client(handler)

    assert await client.get_videos_details([]) == []
    await client._client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize("status", [429, 403])
async def test_rate_limit_is_retried_then_succeeds(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(status, json={})
        return httpx.Response(200, json={"items": [{"id": "a"}]})

    client = _client(handler)

    assert await client.get_videos_details(["a"]) == [{"id": "a"}]
    assert calls == 3
    await client._client.aclose()  # type: ignore[union-attr]


async def test_rate_limit_gives_up_after_five_attempts() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={})

    client = _client(handler)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await client.get_videos_details(["a"])

    assert exc.value.response.status_code == 429
    assert calls == 5
    assert client.quota_used == 0
    await client._client.aclose()  # type: ignore[union-attr]


@pytest.mark.parametrize("status", [400, 401, 404, 500])
async def test_other_errors_are_not_retried(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={})

    client = _client(handler)

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_videos_details(["a"])

    assert calls == 1
    await client._client.aclose()  # type: ignore[union-attr]


async def test_broken_json_response_raises() -> None:
    client = _client(lambda _: httpx.Response(200, content=b"{not json"))

    with pytest.raises(ValueError):
        await client.get_videos_details(["a"])
    await client._client.aclose()  # type: ignore[union-attr]


async def test_non_object_json_becomes_empty_result() -> None:
    client = _client(lambda _: httpx.Response(200, json=[1, 2]))

    assert await client.get_videos_details(["a"]) == []
    await client._client.aclose()  # type: ignore[union-attr]


async def test_use_outside_context_manager_raises() -> None:
    with pytest.raises(RuntimeError, match="context manager"):
        await YouTubeClient("K").get_videos_details(["a"])


async def test_async_context_manager_opens_and_closes_real_client() -> None:
    async with YouTubeClient("K") as client:
        assert client._client is not None
        inner = client._client
        assert not inner.is_closed

    assert inner.is_closed


async def test_second_identical_call_is_served_from_cache(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"items": [{"id": "a"}]})

    client = _client(handler, cache)
    first = await client.get_videos_details(["a"])
    await db.trigger_maintenance()
    second = await client.get_videos_details(["a"])

    assert first == second == [{"id": "a"}]
    assert calls == 1
    assert client.quota_used == 1
    await client._client.aclose()  # type: ignore[union-attr]


async def test_api_key_is_never_stored_in_cache(db: Database) -> None:
    cache = YouTubeCache(db)
    await cache.init_tables()
    client = _client(lambda _: httpx.Response(200, json={"items": []}), cache)

    await client.get_videos_details(["a"])
    await db.trigger_maintenance()

    conn = await db.get_reader()
    async with conn.execute(
        "SELECT cache_key, response_json FROM youtube_cache"
    ) as cur:
        rows = await cur.fetchall()
    await conn.close()
    row_list = list(rows)
    assert len(row_list) == 1
    assert "KEY" not in row_list[0][0] and "KEY" not in row_list[0][1]
    await client._client.aclose()  # type: ignore[union-attr]
