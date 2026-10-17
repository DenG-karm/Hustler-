import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import structlog

from services.core.hustler.domain.map_a import analyze_transcript
from services.core.hustler.orchestration.map_b import MapBExecutor
from services.core.hustler.orchestration.reduce import ReduceOrchestrator
from services.core.hustler.storage.jobs import JobRepository, JobStatus

logger = structlog.get_logger()

ProgressCallback = Callable[[int], Awaitable[None]]
# (job_id, rapor) -> çıktı dosyası yolu. rapor(0..100) render ilerlemesini bildirir.
RenderStep = Callable[[str, ProgressCallback], Awaitable[str]]

PROGRESS_MAP_A = (5, 20)
PROGRESS_REDUCE = (25, 45)
PROGRESS_MAP_B = (50, 65)
PROGRESS_RENDER = (70, 99)


@dataclass(frozen=True)
class PipelineVideo:
    video_id: str
    transcript: str
    duration_seconds: int


@dataclass
class PipelineResult:
    job_id: str
    status: JobStatus
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    rejected: dict[str, str] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    analyses: list[dict[str, object]] = field(default_factory=list)


def _scale(span: tuple[int, int], done: int, total: int) -> int:
    lo, hi = span
    return lo + (hi - lo) * done // max(total, 1)


class PipelineOrchestrator:
    """
    Map A -> Reduce -> Map B -> (Render) zincirini sırayla çalıştırır ve her aşamada
    jobs tablosunu günceller:
      DISCOVERY (Map A) -> GENERATING (Reduce + Map B) -> RENDERING -> COMPLETED | FAILED
    Hata asla yutulmaz: iş FAILED olur ve error_message'a yazılır.
    """

    def __init__(
        self,
        jobs: JobRepository,
        reduce: ReduceOrchestrator,
        map_b: MapBExecutor,
        render: Optional[RenderStep] = None,
        use_local_model: bool = False,
    ):
        self.jobs = jobs
        self.reduce = reduce
        self.map_b = map_b
        self.render = render
        self.use_local_model = use_local_model

    async def run(self, job_id: str, videos: list[PipelineVideo]) -> PipelineResult:
        result = PipelineResult(job_id=job_id, status=JobStatus.PENDING)
        try:
            await self._run(job_id, videos, result)
        except asyncio.CancelledError:
            await self._fail(job_id, result, "İptal edildi")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("pipeline_failed", job_id=job_id, error=str(exc))
            await self._fail(job_id, result, f"{type(exc).__name__}: {exc}")
        return result

    async def _fail(self, job_id: str, result: PipelineResult, message: str) -> None:
        message = message[:1000]
        result.status = JobStatus.FAILED
        result.error_message = message
        await self.jobs.update(job_id, JobStatus.FAILED, error_message=message)

    async def _stage_map_a(
        self, job_id: str, videos: list[PipelineVideo], result: PipelineResult
    ) -> list[PipelineVideo] | None:
        await self.jobs.update(job_id, JobStatus.DISCOVERY, PROGRESS_MAP_A[0], "Map A: aday filtreleme")
        accepted: list[PipelineVideo] = []
        for v in videos:
            verdict = analyze_transcript(v.transcript, v.duration_seconds)
            if verdict.is_accepted:
                accepted.append(v)
            else:
                result.rejected[v.video_id] = verdict.rejection_reason or "reddedildi"
        if not accepted:
            reasons = "; ".join(f"{k}: {r}" for k, r in result.rejected.items()) or "aday yok"
            await self._fail(job_id, result, f"Map A hiçbir adayı kabul etmedi ({reasons})")
            return None
        await self.jobs.update(job_id, JobStatus.DISCOVERY, PROGRESS_MAP_A[1], "Map A tamamlandı")
        return accepted

    async def _stage_reduce(
        self, job_id: str, accepted: list[PipelineVideo], result: PipelineResult
    ) -> list[PipelineVideo] | None:
        await self.jobs.update(job_id, JobStatus.GENERATING, PROGRESS_REDUCE[0], "Reduce: analiz")
        reduced: list[PipelineVideo] = []
        for i, v in enumerate(accepted, start=1):
            try:
                result.analyses.append({"video_id": v.video_id, **await self.reduce.analyze(v.transcript)})
                reduced.append(v)
            except Exception as exc:  # noqa: BLE001
                result.failed[v.video_id] = f"Reduce: {type(exc).__name__}: {exc}"
            await self.jobs.update(
                job_id, JobStatus.GENERATING, _scale(PROGRESS_REDUCE, i, len(accepted)), "Reduce: analiz"
            )
        if not reduced:
            await self._fail(job_id, result, f"Reduce hiçbir videoyu işleyemedi ({_join(result.failed)})")
            return None
        return reduced

    async def _stage_map_b(
        self, job_id: str, reduced: list[PipelineVideo], result: PipelineResult
    ) -> bool:
        await self.jobs.update(job_id, JobStatus.GENERATING, PROGRESS_MAP_B[0], "Map B: kanca analizi")
        outputs = await self.map_b.execute_batch(
            [{"video_id": v.video_id, "transcript": v.transcript} for v in reduced],
            use_local_model=self.use_local_model,
        )
        succeeded = 0
        for out in outputs:
            if out.get("status") == "SUCCESS":
                succeeded += 1
            else:
                result.failed[str(out["video_id"])] = f"Map B: {out.get('error')}"
        if succeeded == 0:
            await self._fail(job_id, result, f"Map B hiçbir videoyu işleyemedi ({_join(result.failed)})")
            return False
        await self.jobs.update(job_id, JobStatus.GENERATING, PROGRESS_MAP_B[1], "Map B tamamlandı")
        return True

    async def _stage_render(self, job_id: str) -> str | None:
        if self.render is None:
            return None
        await self.jobs.update(job_id, JobStatus.RENDERING, PROGRESS_RENDER[0], "Render")

        async def report(pct: int) -> None:
            pct = max(0, min(100, pct))
            await self.jobs.update(job_id, JobStatus.RENDERING, _scale(PROGRESS_RENDER, pct, 100), "Render")

        return await self.render(job_id, report)

    async def _run(self, job_id: str, videos: list[PipelineVideo], result: PipelineResult) -> None:
        accepted = await self._stage_map_a(job_id, videos, result)
        if accepted is None:
            return

        reduced = await self._stage_reduce(job_id, accepted, result)
        if reduced is None:
            return

        if not await self._stage_map_b(job_id, reduced, result):
            return

        output_path = await self._stage_render(job_id)

        await self.jobs.update(job_id, JobStatus.COMPLETED, output_path=output_path, current_step="Tamamlandı")
        result.status = JobStatus.COMPLETED
        result.output_path = output_path


def _join(failures: dict[str, str]) -> str:
    return "; ".join(f"{k}: {v}" for k, v in failures.items())
