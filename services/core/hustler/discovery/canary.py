"""yt-dlp Kanarya Sondası ve Güncelleme Politikası (K-806)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from pydantic import BaseModel, Field

DEFAULT_CANARY_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
_WIN32_NO_WINDOW: int = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class CanaryStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED_EXTRACTOR_BROKEN = "DEGRADED_EXTRACTOR_BROKEN"
    BINARY_MISSING = "BINARY_MISSING"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"


class ChecksumMismatchError(Exception):
    """İndirilen binary SHA-256 sağlama toplamı eşleşmediğinde fırlatılır."""


class CanaryReport(BaseModel):  # type: ignore[explicit-any]
    status: CanaryStatus
    ytdlp_version: str | None = None
    latency_ms: float = 0.0
    error_detail: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def validate_extractor_payload(payload: object) -> CanaryStatus:
    """yt-dlp çıktısının zorunlu kontrat alanlarını (id, title, duration/webpage_url) denetler."""
    if not isinstance(payload, dict):
        return CanaryStatus.SCHEMA_MISMATCH
    v_id, title = payload.get("id"), payload.get("title")
    if not (isinstance(v_id, str) and v_id.strip() and isinstance(title, str) and title.strip()):
        return CanaryStatus.SCHEMA_MISMATCH
    dur, url = payload.get("duration"), payload.get("webpage_url")
    if not ((isinstance(dur, (int, float)) and dur > 0) or (isinstance(url, str) and url.strip())):
        return CanaryStatus.SCHEMA_MISMATCH
    return CanaryStatus.HEALTHY


def _resolve_ytdlp_cmd(custom_binary: Path | str | None = None) -> list[str] | None:
    """yt-dlp komutunu veya dev ortamında Python modül çağrısını çözümler."""
    if custom_binary:
        p = Path(custom_binary)
        if p.exists() and p.is_file():
            return [str(p)]
        which = shutil.which(str(custom_binary))
        return [which] if which else None
    if which := shutil.which("yt-dlp"):
        return [which]
    if getattr(sys, "frozen", False):
        return None  # PyInstaller frozen sidecar fork-bomb koruması
    try:
        importlib.metadata.version("yt_dlp")
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        return None


def run_ytdlp_canary(
    timeout_sec: float = 5.0,
    binary_path: Path | str | None = None,
    test_url: str = DEFAULT_CANARY_URL,
) -> CanaryReport:
    """yt-dlp --version ve çıkarıcı sağlığını test eden, Zero-Crash kanarya sondası."""
    t0 = time.perf_counter()

    def _rep(status: CanaryStatus, ver: str | None = None, err: str | None = None) -> CanaryReport:
        return CanaryReport(
            status=status,
            ytdlp_version=ver,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            error_detail=err,
        )

    try:
        cmd = _resolve_ytdlp_cmd(binary_path)
        if not cmd:
            return _rep(CanaryStatus.BINARY_MISSING, err="yt-dlp binary veya Python modülü bulunamadı.")

        version_str: str | None = None
        if not binary_path and cmd == [sys.executable, "-m", "yt_dlp"]:
            try:
                version_str = importlib.metadata.version("yt_dlp")
            except Exception:
                pass

        if not version_str:
            try:
                p_v = subprocess.run([*cmd, "--version"], capture_output=True, text=True, timeout=timeout_sec, creationflags=_WIN32_NO_WINDOW)
                if p_v.returncode != 0:
                    return _rep(CanaryStatus.BINARY_MISSING, err=f"--version başarısız: {p_v.stderr.strip() or p_v.stdout.strip()}")
                version_str = p_v.stdout.strip()
            except subprocess.TimeoutExpired:
                return _rep(CanaryStatus.DEGRADED_EXTRACTOR_BROKEN, err=f"--version zaman aşımı ({timeout_sec}s)")
            except Exception as e:
                return _rep(CanaryStatus.BINARY_MISSING, err=f"yt-dlp çalıştırılamadı: {e}")

        try:
            p = subprocess.run([*cmd, "--dump-json", "--skip-download", "--no-warnings", "--no-playlist", test_url], capture_output=True, text=True, timeout=timeout_sec, creationflags=_WIN32_NO_WINDOW)
        except subprocess.TimeoutExpired:
            return _rep(CanaryStatus.DEGRADED_EXTRACTOR_BROKEN, version_str, f"Sonda zaman aşımı ({timeout_sec}s)")

        if p.returncode != 0:
            return _rep(CanaryStatus.DEGRADED_EXTRACTOR_BROKEN, version_str, f"Çıkarıcı başarısız: {p.stderr.strip() or p.stdout.strip()}")

        try:
            payload = json.loads(p.stdout)
        except Exception as e:
            return _rep(CanaryStatus.SCHEMA_MISMATCH, version_str, f"JSON ayrıştırma hatası: {e}")

        if validate_extractor_payload(payload) != CanaryStatus.HEALTHY:
            return _rep(CanaryStatus.SCHEMA_MISMATCH, version_str, "Kontrat şema uyumsuzluğu.")

        return _rep(CanaryStatus.HEALTHY, version_str, None)
    except Exception as exc:
        return _rep(CanaryStatus.DEGRADED_EXTRACTOR_BROKEN, None, f"Beklenmeyen sonda hatası (Zero-Crash): {exc}")


async def run_ytdlp_canary_async(
    timeout_sec: float = 5.0,
    binary_path: Path | str | None = None,
    test_url: str = DEFAULT_CANARY_URL,
) -> CanaryReport:
    """Asenkron kanarya sondası."""
    return await asyncio.to_thread(run_ytdlp_canary, timeout_sec, binary_path, test_url)


def verify_binary_checksum(file_path: Path, expected_sha256: str) -> bool:
    """İndirilen binary SHA-256 sağlama toplamını doğrular. Eşleşmezse ChecksumMismatchError fırlatır."""
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Binary dosyası bulunamadı: {file_path}")

    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    calculated = hasher.hexdigest().lower()
    if calculated != expected_sha256.strip().lower():
        raise ChecksumMismatchError(f"SHA-256 uyumsuzluğu! Hesaplanan: {calculated}, Beklenen: {expected_sha256}")
    return True


def _parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(d) for d in re.findall(r"\d+", v)) or (0,)


class UpdatePolicy:
    """yt-dlp binary güncelleme ve sağlama toplamı politikası."""

    CANARY_TIMEOUT_SEC: float = 5.0
    DEFAULT_CANARY_URL: str = DEFAULT_CANARY_URL

    @staticmethod
    def verify_binary_checksum(file_path: Path, expected_sha256: str) -> bool:
        return verify_binary_checksum(file_path, expected_sha256)

    @staticmethod
    def is_update_required(current_ver: str, minimum_ver: str) -> bool:
        """Mevcut sürüm ile asgari sürümü karşılaştırır."""
        return _parse_version(current_ver) < _parse_version(minimum_ver)

    @classmethod
    def apply_verified_binary_update(
        cls, staged_binary: Path, target_binary: Path, expected_sha256: str
    ) -> Path:
        """SHA-256 doğrulamasını yaptıktan sonra hedef binary'yi atomik olarak günceller."""
        cls.verify_binary_checksum(staged_binary, expected_sha256)
        target_binary.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target_binary.with_suffix(target_binary.suffix + ".tmp")
        try:
            shutil.copy2(staged_binary, tmp_target)
            tmp_target.replace(target_binary)
        except Exception:
            if tmp_target.exists():
                tmp_target.unlink(missing_ok=True)
            raise
        return target_binary

