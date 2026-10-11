"""JobRepository: gerçek (geçici) SQLite + WriterQueue; sahte yok."""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from services.core.hustler.db import Database
from services.core.hustler.storage.jobs import (
    JobNotFoundError,
    JobRepository,
    JobStateError,
    JobStatus,
)


@pytest.fixture
async def repo(db: Database) -> JobRepository:
    r = JobRepository(db)
    await r.init_table()
    return r


async def test_create_starts_pending_at_zero(repo: JobRepository) -> None:
    job_id = await repo.create()
    job = await repo.get(job_id)

    assert job is not None
    assert job.status is JobStatus.PENDING
    assert job.progress_pct == 0
    assert job.error_message is None and job.output_path is None
    assert job.created_at == job.updated_at


async def test_init_table_is_idempotent(repo: JobRepository) -> None:
    await repo.init_table()
    await repo.init_table()
    assert await repo.list_recent() == []


async def test_get_unknown_returns_none(repo: JobRepository) -> None:
    assert await repo.get("nope") is None


async def test_update_changes_status_progress_and_step(repo: JobRepository) -> None:
    job_id = await repo.create()
    await repo.update(job_id, JobStatus.GENERATING, 40, "Reduce")
    job = await repo.get(job_id)

    assert job is not None
    assert (job.status, job.progress_pct, job.current_step) == (JobStatus.GENERATING, 40, "Reduce")
    assert job.updated_at >= job.created_at


async def test_update_without_progress_keeps_previous_value(repo: JobRepository) -> None:
    job_id = await repo.create()
    await repo.update(job_id, JobStatus.DISCOVERY, 30, "a")
    await repo.update(job_id, JobStatus.GENERATING, None, None)
    job = await repo.get(job_id)

    assert job is not None
    assert job.progress_pct == 30 and job.current_step == "a"


async def test_completed_forces_100_and_stores_output(repo: JobRepository) -> None:
    job_id = await repo.create()
    await repo.update(job_id, JobStatus.COMPLETED, 12, output_path="C:/out/video.mp4")
    job = await repo.get(job_id)

    assert job is not None
    assert job.progress_pct == 100 and job.output_path == "C:/out/video.mp4"


async def test_failed_keeps_progress_and_error(repo: JobRepository) -> None:
    job_id = await repo.create()
    await repo.update(job_id, JobStatus.RENDERING, 80)
    await repo.update(job_id, JobStatus.FAILED, error_message="ffmpeg çöktü")
    job = await repo.get(job_id)

    assert job is not None
    assert (job.status, job.progress_pct, job.error_message) == (JobStatus.FAILED, 80, "ffmpeg çöktü")


@pytest.mark.parametrize("terminal", [JobStatus.COMPLETED, JobStatus.FAILED])
async def test_terminal_job_cannot_be_changed(repo: JobRepository, terminal: JobStatus) -> None:
    job_id = await repo.create()
    await repo.update(job_id, terminal)

    with pytest.raises(JobStateError):
        await repo.update(job_id, JobStatus.RENDERING, 50)

    job = await repo.get(job_id)
    assert job is not None and job.status is terminal


async def test_update_unknown_job_raises(repo: JobRepository) -> None:
    with pytest.raises(JobNotFoundError):
        await repo.update("ghost", JobStatus.DISCOVERY)


@pytest.mark.parametrize("pct", [-1, 101, 1000])
async def test_progress_out_of_range_is_rejected(repo: JobRepository, pct: int) -> None:
    job_id = await repo.create()

    with pytest.raises(ValueError):
        await repo.update(job_id, JobStatus.DISCOVERY, pct)


async def test_duplicate_job_id_is_rejected_by_primary_key(repo: JobRepository) -> None:
    await repo.create("same")

    with pytest.raises(sqlite3.IntegrityError):
        await repo.create("same")


async def test_db_check_constraint_rejects_unknown_status(db: Database, repo: JobRepository) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        await db.execute_write(
            "INSERT INTO jobs (job_id, status, created_at, updated_at) VALUES ('x', 'BOGUS', 0, 0)"
        )


async def test_list_recent_is_newest_first_and_limited(repo: JobRepository) -> None:
    ids = [await repo.create(f"j{i}") for i in range(5)]

    listed = await repo.list_recent(limit=3)

    assert [j.job_id for j in listed] == [ids[4], ids[3], ids[2]]


async def test_concurrent_updates_never_lock(repo: JobRepository) -> None:
    ids = [await repo.create(f"c{i}") for i in range(10)]

    async def worker(job_id: str) -> None:
        for pct in range(0, 100, 10):
            await repo.update(job_id, JobStatus.GENERATING, pct)
            assert await repo.get(job_id) is not None

    await asyncio.gather(*(worker(i) for i in ids))

    jobs = await repo.list_recent(limit=20)
    assert len(jobs) == 10 and all(j.progress_pct == 90 for j in jobs)


async def test_state_survives_reopening_database(tmp_path: Path) -> None:
    path = tmp_path / "persist.db"
    first = Database(path)
    await first.init()
    repo1 = JobRepository(first)
    await repo1.init_table()
    await repo1.create("keep")
    await repo1.update("keep", JobStatus.RENDERING, 75, "Render")
    await first.close()

    second = Database(path)
    await second.init()
    try:
        job = await JobRepository(second).get("keep")
    finally:
        await second.close()

    assert job is not None and (job.status, job.progress_pct) == (JobStatus.RENDERING, 75)
