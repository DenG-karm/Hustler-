"""ElevenLabsAdapter: gerçek istek/retry/ledger mantığı; yalnızca HTTP taşıma katmanı sahte."""

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from services.core.hustler.infrastructure.tts_port import ElevenLabsAdapter, TTSPort

_RealClient = httpx.AsyncClient


def _install(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    def factory() -> httpx.AsyncClient:
        return _RealClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.fixture(autouse=True)
def _no_wait(fast_retry: Callable[[object], None]) -> None:
    fast_retry(ElevenLabsAdapter.generate_audio_stream)


def test_abstract_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        TTSPort()  # type: ignore[abstract]


async def test_success_writes_audio_sends_exact_request_and_counts_chars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        captured.append(r)
        return httpx.Response(200, content=b"ID3" + b"\x00" * 20_000)

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("KEY123")
    out = tmp_path / "a.mp3"

    await adapter.generate_audio_stream("Merhaba dünya", str(out), "voiceX")

    assert out.read_bytes() == b"ID3" + b"\x00" * 20_000
    assert adapter.get_total_chars_processed() == len("Merhaba dünya")
    req = captured[0]
    assert str(req.url) == "https://api.elevenlabs.io/v1/text-to-speech/voiceX"
    assert req.headers["xi-api-key"] == "KEY123"
    assert json.loads(req.content) == {
        "text": "Merhaba dünya",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }


async def test_ledger_accumulates_across_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, lambda r: httpx.Response(200, content=b"x"))
    adapter = ElevenLabsAdapter("k")

    await adapter.generate_audio_stream("abc", str(tmp_path / "1.mp3"), "v")
    await adapter.generate_audio_stream("de", str(tmp_path / "2.mp3"), "v")

    assert adapter.get_total_chars_processed() == 5


@pytest.mark.parametrize("code", [400, 401, 404, 422])
async def test_permanent_error_raises_value_error_without_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(code, content=b"nope")

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("k")

    with pytest.raises(ValueError, match=f"{code} - nope"):
        await adapter.generate_audio_stream("x", str(tmp_path / "o.mp3"), "v")

    assert calls == 1
    assert adapter.get_total_chars_processed() == 0
    assert not (tmp_path / "o.mp3").exists()


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
async def test_transient_error_is_retried_three_times_then_raised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(code)

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("k")

    with pytest.raises(httpx.HTTPStatusError):
        await adapter.generate_audio_stream("x", str(tmp_path / "o.mp3"), "v")

    assert calls == 3
    assert adapter.get_total_chars_processed() == 0


async def test_429_then_success_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    codes = iter([429, 200])
    _install(monkeypatch, lambda r: httpx.Response(next(codes), content=b"audio"))
    adapter = ElevenLabsAdapter("k")

    await adapter.generate_audio_stream("hey", str(tmp_path / "o.mp3"), "v")

    assert (tmp_path / "o.mp3").read_bytes() == b"audio"
    assert adapter.get_total_chars_processed() == 3


async def test_network_error_is_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = 0

    def handler(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("down", request=r)

    _install(monkeypatch, handler)

    with pytest.raises(httpx.ConnectError):
        await ElevenLabsAdapter("k").generate_audio_stream(
            "x", str(tmp_path / "o.mp3"), "v"
        )

    assert calls == 3


async def test_10k_char_text_is_sent_and_counted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sizes: list[int] = []

    def handler(r: httpx.Request) -> httpx.Response:
        sizes.append(len(json.loads(r.content)["text"]))
        return httpx.Response(200, content=b"x")

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("k")

    await adapter.generate_audio_stream("ş" * 10_000, str(tmp_path / "o.mp3"), "v")

    assert sizes == [10_000]
    assert adapter.get_total_chars_processed() == 10_000
