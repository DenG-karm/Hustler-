from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from services.core.hustler.api.auth import verify_token
from services.core.hustler.storage.jobs import Job, JobRepository, JobStatus

router = APIRouter(dependencies=[Depends(verify_token)])


def _repo(request: Request) -> JobRepository:
    repo = getattr(request.app.state, "job_repo", None)
    if repo:
        return repo
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=500, detail="DB not initialized in app.state")
    return JobRepository(db)


def _serialize(job: Job) -> dict[str, Any]:
    data = asdict(job)
    data["status"] = job.status.value
    return data


@router.get("/jobs")
async def list_jobs(request: Request, limit: int = Query(50, ge=1, le=500)) -> list[dict[str, Any]]:
    """Arayüzün iş listesi / ilerleme çubuğu için son işler."""
    return [_serialize(j) for j in await _repo(request).list_recent(limit)]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    job = await _repo(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    return _serialize(job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    """Hard-Cancel: Çalışan görevi ve bağlı tüm alt süreçleri (FFmpeg vb.) durdurur."""
    repo = _repo(request)
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"İptal edilecek iş bulunamadı: {job_id}")

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"İş zaten sonlanmış durumda ({job.status.value}). Tekrar iptal edilemez."
        )

    # Çalışan arka plan asyncio task'ını iptal et
    running_jobs = getattr(request.app.state, "running_jobs", {})
    task = running_jobs.pop(job_id, None)
    if task and not task.done():
        task.cancel()

    # Veritabanında terminal duruma geç
    await repo.update(job_id, JobStatus.CANCELLED, error_message="Kullanıcı tarafından iptal edildi")

    # Event broker üzerinden iptal olayını yayınla
    broker = getattr(request.app.state, "event_broker", None)
    if broker:
        broker.broadcast("job_cancelled", {
            "job_id": job_id,
            "status": "CANCELLED",
            "message": "Render işlemi kullanıcı tarafından iptal edildi.",
        })

    return {
        "job_id": job_id,
        "status": "CANCELLED",
        "message": "İşlem ve alt süreçler başarıyla iptal edildi.",
    }
