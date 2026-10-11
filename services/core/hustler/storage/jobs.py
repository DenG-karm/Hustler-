import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()


class JobStatus(str, Enum):
    PENDING = "PENDING"
    DISCOVERY = "DISCOVERY"
    GENERATING = "GENERATING"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


class JobNotFoundError(KeyError):
    pass


class JobStateError(RuntimeError):
    """Bitmiş (COMPLETED/FAILED) bir iş değiştirilmeye çalışıldı."""


@dataclass(frozen=True)
class Job:
    job_id: str
    status: JobStatus
    progress_pct: int
    current_step: Optional[str]
    error_message: Optional[str]
    output_path: Optional[str]
    created_at: float
    updated_at: float


_COLUMNS = (
    "job_id, status, progress_pct, current_step, error_message, output_path, created_at, updated_at"
)
_STATUS_LIST = ", ".join(f"'{s.value}'" for s in JobStatus)
_TERMINAL_LIST = ", ".join(f"'{s.value}'" for s in TERMINAL_STATUSES)


class JobRepository:
    """
    Üretim işlerinin durum takibi. Tüm yazmalar Database.WriterQueue üzerinden geçer;
    arayüz ilerleme çubuğunu bu tablodan (sidecar API'si üzerinden) okur.
    """

    def __init__(self, db: Database):
        self.db = db

    async def init_table(self) -> None:
        await self.db.execute_write(
            f"""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ({_STATUS_LIST})),
                progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
                current_step TEXT,
                error_message TEXT,
                output_path TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        await self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

    async def reap_zombies(self) -> None:
        """Sistem çökmesi sonucu yarım kalmış işleri (Zombie) temizler."""
        await self.db.execute_write(
            "UPDATE jobs SET status = ?, error_message = ? WHERE status IN (?, ?, ?, ?)",
            (
                JobStatus.FAILED.value,
                "Zombie (sistem çökmesi / zorla kapatma)",
                JobStatus.PENDING.value,
                JobStatus.DISCOVERY.value,
                JobStatus.GENERATING.value,
                JobStatus.RENDERING.value,
            )
        )

    async def create(self, job_id: Optional[str] = None) -> str:
        job_id = job_id or uuid.uuid4().hex
        now = time.time()
        await self.db.execute_write(
            "INSERT INTO jobs (job_id, status, progress_pct, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            (job_id, JobStatus.PENDING.value, now, now),
        )
        return job_id

    async def get(self, job_id: str) -> Optional[Job]:
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                f"SELECT {_COLUMNS} FROM jobs WHERE job_id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
        finally:
            await reader.close()
        return _to_job(row) if row else None

    async def list_recent(self, limit: int = 50) -> list[Job]:
        reader = await self.db.get_reader()
        try:
            async with reader.execute(
                f"SELECT {_COLUMNS} FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
        finally:
            await reader.close()
        return [_to_job(r) for r in rows]

    async def update(
        self,
        job_id: str,
        status: JobStatus,
        progress_pct: Optional[int] = None,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> None:
        if progress_pct is not None and not 0 <= progress_pct <= 100:
            raise ValueError(f"progress_pct 0-100 olmalı: {progress_pct}")

        current = await self.get(job_id)
        if current is None:
            raise JobNotFoundError(job_id)
        if current.status in TERMINAL_STATUSES:
            raise JobStateError(f"{job_id} zaten {current.status.value}; değiştirilemez")

        if status is JobStatus.COMPLETED:
            progress_pct = 100
        elif progress_pct is None:
            progress_pct = current.progress_pct

        await self.db.execute_write(
            f"""
            UPDATE jobs SET status = ?, progress_pct = ?,
                current_step = COALESCE(?, current_step),
                error_message = COALESCE(?, error_message),
                output_path = COALESCE(?, output_path),
                updated_at = ?
            WHERE job_id = ? AND status NOT IN ({_TERMINAL_LIST})
            """,
            (status.value, progress_pct, current_step, error_message, output_path, time.time(), job_id),
        )
        logger.info("job_status", job_id=job_id, status=status.value, progress_pct=progress_pct, step=current_step)


def _to_job(row: tuple[object, ...]) -> Job:
    return Job(
        job_id=str(row[0]),
        status=JobStatus(str(row[1])),
        progress_pct=int(row[2]),  # type: ignore[call-overload]
        current_step=None if row[3] is None else str(row[3]),
        error_message=None if row[4] is None else str(row[4]),
        output_path=None if row[5] is None else str(row[5]),
        created_at=float(row[6]),  # type: ignore[arg-type]
        updated_at=float(row[7]),  # type: ignore[arg-type]
    )
