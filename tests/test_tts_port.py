"""ElevenLabsAdapter: gerçek istek/retry/ledger mantığı; yalnızca HTTP taşıma katmanı sahte."""

import base64
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from services.core.hustler.infrastructure.tts_port import ElevenLabsAdapter, TTSPort
from services.core.hustler.infrastructure.word_alignment import AlignmentError

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


# --- /with-timestamps (kelime zamanlaması) ---------------------------------

def _timed_body(text: str, audio: bytes = b"ID3audio") -> dict[str, object]:
    chars = list(text)
    return {
        "audio_base64": base64.b64encode(audio).decode(),
        "alignment": {
            "characters": chars,
            "character_start_times_seconds": [round(i * 0.05, 3) for i in range(len(chars))],
            "character_end_times_seconds": [round((i + 1) * 0.05, 3) for i in range(len(chars))],
        },
    }


@pytest.fixture(autouse=True)
def _no_wait_timing(fast_retry: Callable[[object], None]) -> None:
    fast_retry(ElevenLabsAdapter.generate_audio_with_timing)


async def test_timing_endpoint_url_body_and_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        captured.append(r)
        return httpx.Response(200, json=_timed_body("bir iki üç"))

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("KEY")
    out = tmp_path / "t.mp3"

    timings = await adapter.generate_audio_with_timing("bir iki üç", str(out), "voiceX")

    req = captured[0]
    assert str(req.url) == "https://api.elevenlabs.io/v1/text-to-speech/voiceX/with-timestamps"
    assert req.headers["xi-api-key"] == "KEY"
    assert json.loads(req.content)["text"] == "bir iki üç"
    assert out.read_bytes() == b"ID3audio"
    assert [(t.word, t.start_ms, t.end_ms) for t in timings] == [
        ("bir", 0, 150),
        ("iki", 200, 350),
        ("üç", 400, 500),
    ]
    assert adapter.get_total_chars_processed() == len("bir iki üç")


@pytest.mark.parametrize("code", [400, 401, 402, 422])
async def test_timing_permanent_error_no_retry_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(code, text="denied")

    _install(monkeypatch, handler)
    adapter = ElevenLabsAdapter("k")

    with pytest.raises(ValueError, match=f"{code} - denied"):
        await adapter.generate_audio_with_timing("x", str(tmp_path / "o.mp3"), "v")

    assert calls == 1
    assert not (tmp_path / "o.mp3").exists()
    assert adapter.get_total_chars_processed() == 0


@pytest.mark.parametrize("code", [429, 503])
async def test_timing_transient_error_retried_three_times(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(code)

    _install(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await ElevenLabsAdapter("k").generate_audio_with_timing("x", str(tmp_path / "o.mp3"), "v")

    assert calls == 3


async def test_timing_transient_then_success_recovers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    codes = iter([503, 200])
    _install(
        monkeypatch,
        lambda r: httpx.Response(next(codes), json=_timed_body("hey")),
    )

    timings = await ElevenLabsAdapter("k").generate_audio_with_timing(
        "hey", str(tmp_path / "o.mp3"), "v"
    )

    assert [t.word for t in timings] == ["hey"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json={"alignment": {}}),
        httpx.Response(200, json={"audio_base64": "!!!notbase64!!!", "alignment": {}}),
        httpx.Response(200, json={"audio_base64": "", "alignment": {}}),
    ],
)
async def test_timing_corrupt_body_raises_value_error_without_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, response: httpx.Response
) -> None:
    _install(monkeypatch, lambda r: response)

    with pytest.raises(ValueError):
        await ElevenLabsAdapter("k").generate_audio_with_timing("x", str(tmp_path / "o.mp3"), "v")

    assert not (tmp_path / "o.mp3").exists()


async def test_timing_missing_alignment_raises_and_writes_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    body = {"audio_base64": base64.b64encode(b"ID3").decode(), "alignment": None}
    _install(monkeypatch, lambda r: httpx.Response(200, json=body))
    adapter = ElevenLabsAdapter("k")

    with pytest.raises(AlignmentError):
        await adapter.generate_audio_with_timing("x", str(tmp_path / "o.mp3"), "v")

    assert not (tmp_path / "o.mp3").exists()
    assert adapter.get_total_chars_processed() == 0


async def test_port_default_timing_is_not_supported() -> None:
    class Plain(TTSPort):
        async def generate_audio_stream(self, text: str, output_path: str, voice_id: str) -> None:
            return None

        def get_total_chars_processed(self) -> int:
            return 0

    with pytest.raises(NotImplementedError):
        await Plain().generate_audio_with_timing("x", "o", "v")