"""AssetManager: gerçek indirme/retry/önbellek mantığı; yalnızca HTTP taşıma katmanı sahte."""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest

from services.core.hustler.infrastructure.asset_manager import (
    AssetManager,
    DownloadRetryError,
)

URL = "https://cdn.example.com/clip.mp4"


@pytest.fixture(autouse=True)
def _no_wait(fast_retry: Callable[[object], None]) -> None:
    fast_retry(AssetManager._download_with_retry)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def manager(tmp_path: Path) -> AssetManager:
    return AssetManager(download_dir=str(tmp_path / "dl"), max_concurrent=2)


async def test_streams_large_body_to_disk_byte_exact(manager: AssetManager) -> None:
    body = bytes(range(256)) * 1000  # 256 KB, birden çok 64KB chunk
    async with _client(lambda r: httpx.Response(200, content=body)) as c:
        path = await manager.download_asset(URL, c)

    assert path.endswith(".mp4")
    assert Path(path).read_bytes() == body
    assert Path(path).name == hashlib.sha256(URL.encode()).hexdigest() + ".mp4"


@pytest.mark.parametrize(
    ("url", "ext"),
    [
        ("https://x/a.webm", ".webm"),
        ("https://x/a", ".mp4"),
        ("https://x/a.verylongext", ".mp4"),
    ],
)
async def test_extension_selection(manager: AssetManager, url: str, ext: str) -> None:
    async with _client(lambda r: httpx.Response(200, content=b"x")) as c:
        path = await manager.download_asset(url, c)

    assert path.endswith(ext)


async def test_cache_hit_makes_no_network_call(manager: AssetManager) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"data")

    async with _client(handler) as c:
        first = await manager.download_asset(URL, c)
        second = await manager.download_asset(URL, c)

    assert first == second
    assert calls == 1


async def test_429_then_success_retries(manager: AssetManager) -> None:
    codes = [429, 503, 200]
    seen: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        code = codes[len(seen)]
        seen.append(code)
        return httpx.Response(code, content=b"ok")

    async with _client(handler) as c:
        path = await manager.download_asset(URL, c)

    assert seen == [429, 503, 200]
    assert Path(path).read_bytes() == b"ok"


async def test_persistent_500_raises_after_four_attempts_and_leaves_no_file(
    manager: AssetManager,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async with _client(handler) as c:
        with pytest.raises(DownloadRetryError, match="500"):
            await manager.download_asset(URL, c)

    assert calls == 4
    assert list(manager.download_dir.iterdir()) == []


async def test_404_is_not_retried(manager: AssetManager) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with _client(handler) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await manager.download_asset(URL, c)

    assert calls == 1


async def test_network_error_is_retried_then_raised(manager: AssetManager) -> None:
    calls = 0

    def handler(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("kopuk", request=r)

    async with _client(handler) as c:
        with pytest.raises(DownloadRetryError, match="Network error"):
            await manager.download_asset(URL, c)

    assert calls == 4


async def test_failed_download_removes_leftover_partial_file(
    manager: AssetManager,
) -> None:
    partial = manager.download_dir / (hashlib.sha256(URL.encode()).hexdigest() + ".mp4")
    partial.write_bytes(b"")  # boş dosya önbellek isabeti sayılmaz

    async with _client(lambda r: httpx.Response(404)) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await manager.download_asset(URL, c)

    assert not partial.exists()


async def test_midstream_failure_removes_partial_file(manager: AssetManager) -> None:
    async def broken() -> AsyncIterator[bytes]:
        yield b"a" * 70_000
        raise httpx.ReadError("yarıda koptu")

    async with _client(lambda r: httpx.Response(200, content=broken())) as c:
        with pytest.raises(DownloadRetryError):
            await manager.download_asset(URL, c)

    assert list(manager.download_dir.iterdir()) == []


async def test_concurrency_is_capped_by_semaphore(manager: AssetManager) -> None:
    active = peak = 0

    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            yield b"x"
            active -= 1

    async with _client(lambda r: httpx.Response(200, stream=Slow())) as c:
        paths = await asyncio.gather(
            *(manager.download_asset(f"https://x/{i}.mp4", c) for i in range(6))
        )

    assert len(set(paths)) == 6
    assert peak == 2
