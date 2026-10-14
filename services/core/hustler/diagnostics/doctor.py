"""
K-803: Sistem Sağlık ve Doctor Motoru (Doctor Report).
- Python ve SQLite sürümlerini raporlar.
- FFmpeg ve yt-dlp ikili erişilebilirlik ve sürümlerini denetler.
- Disk boş alanını (MB) ve veritabanı PRAGMA quick_check durumunu ölçer.
- HEALTHY, DEGRADED veya CRITICAL sistem durumu üretir.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
from typing import Literal, Optional
from pydantic import BaseModel, Field

from services.core.hustler.db.engine import Database


class DoctorReport(BaseModel):  # type: ignore[explicit-any]
    """Sistem sağlık ve bileşen durum raporu."""

    python_version: str
    sqlite_version: str
    ffmpeg_available: bool
    ffmpeg_version: Optional[str] = None
    ytdlp_available: bool
    ytdlp_version: Optional[str] = None
    disk_free_mb: float
    db_quick_check: str
    status: Literal["HEALTHY", "DEGRADED", "CRITICAL"]
    details: dict[str, object] = Field(default_factory=dict)

    @property
    def yt_dlp_available(self) -> bool:
        return self.ytdlp_available

    @property
    def yt_dlp_version(self) -> Optional[str]:
        return self.ytdlp_version

    def __await__(self) -> Generator[object, None, DoctorReport]:
        async def _resolve() -> DoctorReport:
            return self

        return _resolve().__await__()


def run_system_doctor(db: Database) -> DoctorReport:
    """
    Sistemin röntgenini çeker ve yapılandırılmış DoctorReport döner.
    Milisaniyeler içinde çalışır ve asenkron bağlamlarda doğrudan await edilebilir.
    """
    py_ver = platform.python_version()
    sql_ver = sqlite3.sqlite_version

    # 1. FFmpeg Varlık ve Sürüm Denetimi
    ff_path = shutil.which("ffmpeg")
    ff_avail = bool(ff_path)
    ff_ver: Optional[str] = None
    if ff_path:
        try:
            res = subprocess.run(
                [ff_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                ff_ver = res.stdout.splitlines()[0].strip()
        except Exception:
            pass

    # 2. yt-dlp Varlık ve Sürüm Denetimi
    yt_path = shutil.which("yt-dlp")
    yt_avail = bool(yt_path)
    yt_ver: Optional[str] = None
    if yt_path:
        try:
            res = subprocess.run(
                [yt_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                yt_ver = res.stdout.strip()
        except Exception:
            pass

    # 3. Disk Boş Alan Denetimi (MB)
    target_dir = db.path.parent if db.path.parent.exists() else Path.cwd()
    try:
        usage = shutil.disk_usage(target_dir)
        disk_free = round(usage.free / (1024 * 1024), 2)
    except Exception:
        disk_free = 0.0

    # 4. Veritabanı PRAGMA quick_check
    db_qc = "ok"
    if db.path.exists():
        try:
            conn = sqlite3.connect(f"file:{db.path.resolve()}?mode=ro", uri=True, timeout=5.0)
            try:
                cur = conn.execute("PRAGMA quick_check;")
                row = cur.fetchone()
                db_qc = str(row[0]) if row else "unknown"
            finally:
                conn.close()
        except Exception as e:
            db_qc = f"error: {e}"
    else:
        db_qc = "not_created"

    # 5. Sağlık Durumu Kararı
    if db_qc not in ("ok", "not_created"):
        status: Literal["HEALTHY", "DEGRADED", "CRITICAL"] = "CRITICAL"
    elif disk_free < 500.0:
        status = "CRITICAL"
    elif not ff_avail or not yt_avail or disk_free < 2048.0:
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    return DoctorReport(
        python_version=py_ver,
        sqlite_version=sql_ver,
        ffmpeg_available=ff_avail,
        ffmpeg_version=ff_ver,
        ytdlp_available=yt_avail,
        ytdlp_version=yt_ver,
        disk_free_mb=disk_free,
        db_quick_check=db_qc,
        status=status,
    )


async def async_run_system_doctor(db: Database) -> DoctorReport:
    """Asenkron çağrılar için iş parçacığı havuzu sarmalayıcısı."""
    return await asyncio.to_thread(run_system_doctor, db)
