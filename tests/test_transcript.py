"""TranscriptProvider: youtube_transcript_api sahtelenir; ağ yok."""

import asyncio
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch

import pytest
from youtube_transcript_api import TranscriptsDisabled, VideoUnavailable

from services.core.hustler.providers import transcript as transcript_mod
from services.core.hustler.providers.transcript import TranscriptProvider, TranscriptResult


@dataclass
class FakeSnippet:
    text: str


@dataclass
class FakeTranscript:
    language_code: str
    is_generated: bool
    snippets: list[FakeSnippet]

    def fetch(self) -> list[FakeSnippet]:
        return self.snippets


class FakeApi:
    def __init__(
        self,
        transcripts: Optional[list[FakeTranscript]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self._transcripts = transcripts or []
        self._error = error

    def list(self, video_id: str) -> list[FakeTranscript]:
        if self._error is not None:
            raise self._error
        return self._transcripts


def _patched(api: FakeApi) -> AbstractContextManager[object]:
    return patch.object(transcript_mod, "YouTubeTranscriptApi", lambda: api)


async def test_manual_transcript_is_preferred_over_generated() -> None:
    api = FakeApi(
        [
            FakeTranscript("en", True, [FakeSnippet("auto")]),
            FakeTranscript("en", False, [FakeSnippet("hello"), FakeSnippet("world")]),
        ]
    )
    with _patched(api):
        res = await TranscriptProvider("en").get_transcript("vid1")

    assert isinstance(res, TranscriptResult)
    assert res.text == "hello world"
    assert res.requires_whisper is False
    assert res.translation_required is False
    assert res.error_message is None


async def test_generated_transcript_is_used_when_no_manual_exists() -> None:
    api = FakeApi([FakeTranscript("tr", True, [FakeSnippet("merhaba")])])
    with _patched(api):
        res = await TranscriptProvider("en").get_transcript("vid2")

    assert res.text == "merhaba"
    assert res.language_code == "tr"
    assert res.translation_required is True


async def test_video_without_any_transcript_is_routed_to_whisper() -> None:
    with _patched(FakeApi([])):
        res = await TranscriptProvider().get_transcript("vid3")

    assert res.requires_whisper is True
    assert res.text is None
    assert res.error_message == "No transcripts found"


@pytest.mark.parametrize(
    "error_factory", [lambda: TranscriptsDisabled("v"), lambda: VideoUnavailable("v")]
)
async def test_disabled_or_unavailable_video_falls_back_to_whisper_without_raising(
    error_factory: "type[Exception] | object",
) -> None:
    error = error_factory()  # type: ignore[operator]
    assert isinstance(error, Exception)
    with _patched(FakeApi(error=error)):
        res = await TranscriptProvider().get_transcript("vid4")

    assert res.requires_whisper is True
    assert res.error_message == type(error).__name__


async def test_unexpected_error_such_as_rate_limit_does_not_crash_flow() -> None:
    with _patched(FakeApi(error=RuntimeError("429 Too Many Requests"))):
        res = await TranscriptProvider().get_transcript("vid5")

    assert res.requires_whisper is True
    assert res.error_message is not None
    assert "429" in res.error_message


async def test_parallel_lookups_do_not_block_event_loop() -> None:
    api = FakeApi([FakeTranscript("en", False, [FakeSnippet("x")])])
    provider = TranscriptProvider("en")
    with _patched(api):
        start = time.perf_counter()
        results = await asyncio.wait_for(
            asyncio.gather(*(provider.get_transcript(f"v{i}") for i in range(10))),
            timeout=5,
        )
        elapsed = time.perf_counter() - start

    assert len(results) == 10
    assert all(r.text == "x" for r in results)
    assert elapsed < 2.0
