"""YouTubeDownloader: gerçek argüman/URL/çıktı mantığı; yalnızca yt-dlp alt süreci sahtelenir."""

import asyncio
from pathlib import Path

import pytest

from services.core.hustler.infrastructure.youtube_downloader import (
    YouTubeDownloader,
    YouTubeDownloadError,
    validate_youtube_url,
)

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


class FakeProc:
    def __init__(self, returncode: int, out: bytes = b"", err: bytes = b"", hang: bool = False) -> None:
        self.returncode: int | None = returncode
        self._out, self._err, self._hang = out, err, hang
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hang:
            await asyncio.sleep(60)
        return self._out, self._err

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return 0


def _patch_spawn(monkeypatch: pytest.MonkeyPatch, proc: FakeProc) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    async def fake(*args: str, **kwargs: object) -> FakeProc:
        calls.append(args)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake)
    return calls


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/watch?v=x",
        "https://evil.example.com/watch?v=x",
        "https://youtube.com.evil.example/watch?v=x",
        "--exec=calc",
        "file:///C:/secret.mp4",
        "",
    ],
)
def test_rejects_non_youtube_or_non_https_urls(url: str) -> None:
    with pytest.raises(ValueError, match="YouTube"):
        validate_youtube_url(url)


@pytest.mark.parametrize("host", ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"])
def test_accepts_youtube_hosts(host: str) -> None:
    url = f"https://{host}/watch?v=abc"
    assert validate_youtube_url(url) == url


def test_audio_args_extract_mp3_and_terminate_options_before_url() -> None:
    args = YouTubeDownloader.build_args(URL, "audio", "out/%(id)s.%(ext)s")

    assert args[-2:] == ["--", URL]
    assert args[args.index("-x") : args.index("-x") + 3] == ["-x", "--audio-format", "mp3"]
    assert "--no-playlist" in args


def test_video_args_merge_to_mp4_capped_at_1080p() -> None:
    args = YouTubeDownloader.build_args(URL, "video", "o")

    assert args[args.index("--merge-output-format") + 1] == "mp4"
    assert "height<=1080" in args[args.index("-f") + 1]
    assert "-x" not in args


async def test_download_returns_path_printed_by_ytdlp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    media = tmp_path / "dl" / "abc.mp3"
    media.parent.mkdir()
    media.write_bytes(b"ID3data")
    calls = _patch_spawn(monkeypatch, FakeProc(0, out=f"{media}\n".encode()))

    path = await YouTubeDownloader(str(tmp_path / "dl")).download(URL, "audio")

    assert path == str(media)
    assert URL in calls[0] and "mp3" in calls[0]


async def test_download_failure_includes_exit_code_and_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_spawn(monkeypatch, FakeProc(1, err=b"ERROR: Video unavailable"))

    with pytest.raises(YouTubeDownloadError, match="1.*Video unavailable"):
        await YouTubeDownloader(str(tmp_path)).download(URL)


async def test_download_fails_when_reported_file_is_missing_or_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    empty = tmp_path / "empty.mp3"
    empty.write_bytes(b"")
    _patch_spawn(monkeypatch, FakeProc(0, out=f"{empty}\n".encode()))

    with pytest.raises(YouTubeDownloadError, match="bulunamadı"):
        await YouTubeDownloader(str(tmp_path)).download(URL)


async def test_timeout_kills_the_child_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proc = FakeProc(0, hang=True)
    _patch_spawn(monkeypatch, proc)

    with pytest.raises(asyncio.TimeoutError):
        await YouTubeDownloader(str(tmp_path), timeout_sec=0.05).download(URL)

    assert proc.killed


async def test_invalid_url_never_spawns_a_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch_spawn(monkeypatch, FakeProc(0))

    with pytest.raises(ValueError):
        await YouTubeDownloader(str(tmp_path)).download("https://evil.example/x")

    assert calls == []
