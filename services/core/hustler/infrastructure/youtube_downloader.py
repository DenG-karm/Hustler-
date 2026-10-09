import asyncio
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger()

_ALLOWED_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})
_ERROR_TAIL_CHARS = 800

MediaKind = Literal["audio", "video"]


class YouTubeDownloadError(Exception):
    """yt-dlp indirmesi başarısız oldu (çıkış kodu ve stderr kuyruğu mesajda)."""


def validate_youtube_url(url: str) -> str:
    """Yalnızca https YouTube bağlantılarını kabul eder (rastgele host / seçenek enjeksiyonu engeli)."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"Geçerli bir https YouTube URL'si gerekli: {url[:80]!r}")
    return url


class YouTubeDownloader:
    """
    yt-dlp tabanlı YouTube indirici. Bloklamamak için yt-dlp ayrı bir süreç olarak
    (asyncio subprocess) çalıştırılır; zaman aşımı/iptalde süreç öldürülür.
    Ses için mp3'e dönüştürme (-x --audio-format mp3), video için mp4 birleştirme yapılır.
    """

    def __init__(self, download_dir: str = "downloads", timeout_sec: float = 300.0) -> None:
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_sec = timeout_sec

    @staticmethod
    def build_args(url: str, kind: MediaKind, out_template: str) -> list[str]:
        args = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist", "--no-warnings", "--no-progress",
            "--no-simulate", "--print", "after_move:filepath",
            "-o", out_template,
        ]
        if kind == "audio":
            args += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3"]
        else:
            args += [
                "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                "--merge-output-format", "mp4",
            ]
        return [*args, "--", url]

    async def download(self, url: str, kind: MediaKind = "audio") -> str:
        validate_youtube_url(url)
        template = str(self.download_dir / "%(id)s.%(ext)s")
        proc = await asyncio.create_subprocess_exec(
            *self.build_args(url, kind, template),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_sec)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            await proc.wait()
            raise

        if proc.returncode != 0:
            tail = err.decode("utf-8", errors="replace").strip()[-_ERROR_TAIL_CHARS:]
            raise YouTubeDownloadError(f"yt-dlp çıkış kodu {proc.returncode}: {tail}")

        lines = [ln.strip() for ln in out.decode("utf-8", errors="replace").splitlines() if ln.strip()]
        path = Path(lines[-1]) if lines else None
        if path is None or not path.is_file() or path.stat().st_size == 0:
            raise YouTubeDownloadError(f"yt-dlp çıktı dosyası bulunamadı: {lines[-1:] }")
        logger.info("youtube_download_ok", path=str(path), kind=kind, bytes=path.stat().st_size)
        return str(path)
