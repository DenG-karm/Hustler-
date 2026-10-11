"""PipelineOrchestrator: gerçek Map A/Reduce/Map B/JobRepository/SQLite; yalnızca LLM HTTP sahte."""

import asyncio
from collections.abc import AsyncIterator
from typing import Optional

import pytest

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.llm_port import LLMResponse
from services.core.hustler.orchestration.map_b import MapBExecutor
from services.core.hustler.orchestration.pipeline import (
    PipelineOrchestrator,
    PipelineVideo,
)
from services.core.hustler.orchestration.reduce import ReduceOrchestrator
from services.core.hustler.storage.jobs import JobRepository, JobStatus
from tests.conftest import LLMFactory

GOOD_TEXT = " ".join(f"kelime{i}" for i in range(100))  # 100 kelime / 40 sn = 150 WPM


def good(video_id: str, tag: str = "") -> PipelineVideo:
    return PipelineVideo(video_id, f"{tag} {GOOD_TEXT}", 40)


class SpyJobs(JobRepository):
    """Gerçek yazmaları yapar; ayrıca (durum, ilerleme) geçmişini kaydeder."""

    def __init__(self, db: Database) -> None:
        super().__init__(db)
        self.history: list[tuple[JobStatus, int]] = []

    async def update(self, job_id: str, status: JobStatus, progress_pct: Optional[int] = None, *args: object, **kw: object) -> None:  # type: ignore[override]
        await super().update(job_id, status, progress_pct, *args, **kw)  # type: ignore[arg-type]
        job = await self.get(job_id)
        assert job is not None
        self.history.append((job.status, job.progress_pct))


@pytest.fixture
async def jobs(db: Database) -> AsyncIterator[SpyJobs]:
    repo = SpyJobs(db)
    await repo.init_table()
    yield repo


async def _build(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory, render: object = None
) -> tuple[PipelineOrchestrator, list[str]]:
    harness = llm_factory(["analiz sonucu"])
    reduce = ReduceOrchestrator(db, harness.port)
    await reduce.init_table()
    pipe = PipelineOrchestrator(jobs, reduce, MapBExecutor(llm_port=harness.port), render=render)  # type: ignore[arg-type]
    return pipe, harness.prompts


async def test_happy_path_walks_every_status_in_order_and_ends_completed(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    async def render(job_id: str, report: object) -> str:
        for pct in (0, 50, 100):
            await report(pct)  # type: ignore[operator]
        return "C:/out/final.mp4"

    pipe, prompts = await _build(db, jobs, llm_factory, render)
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1", "a"), good("v2", "b")])

    assert result.status is JobStatus.COMPLETED
    assert result.output_path == "C:/out/final.mp4"
    statuses = [s for s, _ in jobs.history]
    order = [JobStatus.DISCOVERY, JobStatus.GENERATING, JobStatus.RENDERING, JobStatus.COMPLETED]
    assert [s for i, s in enumerate(statuses) if i == 0 or s != statuses[i - 1]] == order
    pcts = [p for _, p in jobs.history]
    assert pcts == sorted(pcts) and pcts[-1] == 100
    final = await jobs.get(job_id)
    assert final is not None
    assert (final.status, final.progress_pct, final.output_path) == (
        JobStatus.COMPLETED, 100, "C:/out/final.mp4",
    )
    assert len(prompts) == 4  # 2 video x (Reduce + Map B)
    assert {a["video_id"] for a in result.analyses} == {"v1", "v2"}


async def test_render_progress_is_mapped_into_70_99_band(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    async def render(job_id: str, report: object) -> str:
        await report(0)  # type: ignore[operator]
        await report(100)  # type: ignore[operator]
        await report(999)  # type: ignore[operator]  # taşan değer kırpılır
        return "out.mp4"

    pipe, _ = await _build(db, jobs, llm_factory, render)
    job_id = await jobs.create()
    await pipe.run(job_id, [good("v1")])

    render_pcts = [p for s, p in jobs.history if s is JobStatus.RENDERING]
    assert render_pcts[0] == 70 and render_pcts[-1] == 99
    assert all(70 <= p <= 99 for p in render_pcts)


async def test_pipeline_without_render_completes_with_no_output(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    pipe, _ = await _build(db, jobs, llm_factory)
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1")])

    assert result.status is JobStatus.COMPLETED and result.output_path is None
    assert JobStatus.RENDERING not in [s for s, _ in jobs.history]


@pytest.mark.parametrize(
    "videos",
    [
        [],
        [PipelineVideo("short", "az kelime", 30)],
        [PipelineVideo("zero", GOOD_TEXT, 0)],
        [PipelineVideo("neg", GOOD_TEXT, -5)],
        [PipelineVideo("empty", "", 30)],
        [PipelineVideo("slow", GOOD_TEXT, 3600)],
        [PipelineVideo("fast", GOOD_TEXT, 5)],
    ],
)
async def test_map_a_rejecting_everything_fails_job_without_calling_llm(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory, videos: list[PipelineVideo]
) -> None:
    pipe, prompts = await _build(db, jobs, llm_factory)
    job_id = await jobs.create()

    result = await pipe.run(job_id, videos)

    assert result.status is JobStatus.FAILED
    assert "Map A" in (result.error_message or "")
    assert prompts == []
    job = await jobs.get(job_id)
    assert job is not None and job.status is JobStatus.FAILED
    assert "Map A" in (job.error_message or "")


async def test_partial_rejection_is_reported_but_job_completes(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    pipe, _ = await _build(db, jobs, llm_factory)
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("ok"), PipelineVideo("bad", "kısa", 30)])

    assert result.status is JobStatus.COMPLETED
    assert set(result.rejected) == {"bad"}


async def test_llm_failure_marks_job_failed_with_reason(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    harness = llm_factory([RuntimeError("LLM çöktü")])
    reduce = ReduceOrchestrator(db, harness.port)
    await reduce.init_table()
    pipe = PipelineOrchestrator(jobs, reduce, MapBExecutor(llm_port=harness.port))
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1")])

    assert result.status is JobStatus.FAILED
    assert "Reduce" in (result.error_message or "") and "LLM çöktü" in (result.error_message or "")
    job = await jobs.get(job_id)
    assert job is not None and job.status is JobStatus.FAILED
    assert "LLM çöktü" in (job.error_message or "")


async def test_one_bad_video_does_not_sink_the_batch(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = llm_factory(["x"])

    async def fake(prompt: str) -> LLMResponse:
        if "ZEHIR" in prompt:
            raise RuntimeError("bu video bozuk")
        return LLMResponse("ok", 1, 1, 2)

    monkeypatch.setattr(harness.port, "_execute_network_request", fake)
    reduce = ReduceOrchestrator(db, harness.port)
    await reduce.init_table()
    pipe = PipelineOrchestrator(jobs, reduce, MapBExecutor(llm_port=harness.port))
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("fine", "a"), good("poison", "ZEHIR")])

    assert result.status is JobStatus.COMPLETED
    assert "poison" in result.failed and "bu video bozuk" in result.failed["poison"]
    assert [a["video_id"] for a in result.analyses] == ["fine"]


async def test_map_b_total_failure_fails_job(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = llm_factory(["x"])

    async def fake(prompt: str) -> LLMResponse:
        if "kancayı çıkar" in prompt:
            raise RuntimeError("map b down")
        return LLMResponse("ok", 1, 1, 2)

    monkeypatch.setattr(harness.port, "_execute_network_request", fake)
    reduce = ReduceOrchestrator(db, harness.port)
    await reduce.init_table()
    pipe = PipelineOrchestrator(jobs, reduce, MapBExecutor(llm_port=harness.port))
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1")])

    assert result.status is JobStatus.FAILED and "Map B" in (result.error_message or "")


async def test_render_failure_marks_failed_and_keeps_last_progress(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    async def render(job_id: str, report: object) -> str:
        await report(50)  # type: ignore[operator]
        raise RuntimeError("NVENC düştü")

    pipe, _ = await _build(db, jobs, llm_factory, render)
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1")])

    assert result.status is JobStatus.FAILED
    job = await jobs.get(job_id)
    assert job is not None
    assert job.status is JobStatus.FAILED and "NVENC düştü" in (job.error_message or "")
    assert job.progress_pct == 84  # 70 + 29*50//100 = 84; hata anındaki ilerleme korunur


async def test_error_message_is_truncated_to_1000_chars(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    async def render(job_id: str, report: object) -> str:
        raise RuntimeError("x" * 5000)

    pipe, _ = await _build(db, jobs, llm_factory, render)
    job_id = await jobs.create()

    result = await pipe.run(job_id, [good("v1")])

    assert result.error_message is not None and len(result.error_message) == 1000


async def test_cancellation_marks_job_failed_and_propagates(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    started = asyncio.Event()

    async def render(job_id: str, report: object) -> str:
        started.set()
        await asyncio.sleep(60)
        return "never"

    pipe, _ = await _build(db, jobs, llm_factory, render)
    job_id = await jobs.create()
    task = asyncio.create_task(pipe.run(job_id, [good("v1")]))
    await asyncio.wait_for(started.wait(), 10)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    job = await jobs.get(job_id)
    assert job is not None
    assert job.status is JobStatus.FAILED and job.error_message == "İptal edildi"


async def test_reduce_cache_means_second_job_makes_no_reduce_llm_call(
    db: Database, jobs: SpyJobs, llm_factory: LLMFactory
) -> None:
    pipe, prompts = await _build(db, jobs, llm_factory)
    video = good("v1")

    await pipe.run(await jobs.create(), [video])
    first = len(prompts)
    await pipe.run(await jobs.create(), [video])

    assert first == 2 and len(prompts) == 3  # ikinci koşuda yalnızca Map B çağrılır
