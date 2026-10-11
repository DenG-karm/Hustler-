"""K-703: Hard-Cancel API, Event Broker ve RFC 7807 Problem Details Testleri."""

import asyncio
from pathlib import Path
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient

from services.core.hustler.main import app, SESSION_TOKEN
from services.core.hustler.db import Database
from services.core.hustler.storage.jobs import JobRepository, JobStatus
from services.core.hustler.infrastructure.event_broker import EventBroker


@pytest.fixture
async def test_env(tmp_path: Path) -> AsyncGenerator[tuple[JobRepository, EventBroker], None]:
    db = Database(tmp_path / "test_cancel.db")
    await db.init()
    repo = JobRepository(db)
    await repo.init_table()
    broker = EventBroker()

    app.state.session_token = SESSION_TOKEN
    app.state.db = db
    app.state.job_repo = repo
    app.state.event_broker = broker
    app.state.running_jobs = {}

    yield repo, broker

    await db.close()


@pytest.fixture
async def client(test_env: tuple[JobRepository, EventBroker]) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_cancel_running_job_broadcasts_and_updates_status(
    client: AsyncClient, test_env: tuple[JobRepository, EventBroker]
) -> None:
    repo, broker = test_env

    job_id = await repo.create()
    await repo.update(job_id, JobStatus.RENDERING, 30)

    # Simüle edilmiş arka plan görevi ekleyelim
    async def dummy_render() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    task = asyncio.create_task(dummy_render())
    app.state.running_jobs[job_id] = task

    # Event Broker abonesi
    events_received: list[str] = []

    async def listener() -> None:
        async for evt in broker.subscribe():
            events_received.append(evt)
            if "job_cancelled" in evt:
                break

    listener_task = asyncio.create_task(listener())

    # Cancel API çağrısı
    resp = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "CANCELLED"

    # Görevin iptal edildiğini doğrula
    assert task.cancelled() or task.done()
    assert job_id not in app.state.running_jobs

    # DB durumunu doğrula
    job = await repo.get(job_id)
    assert job is not None
    assert job.status is JobStatus.CANCELLED

    # Event broker olayını bekle
    await asyncio.wait_for(listener_task, timeout=2.0)
    assert any("job_cancelled" in e and job_id in e for e in events_received)


@pytest.mark.asyncio
async def test_cancel_unknown_job_returns_rfc7807_problem_details(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/jobs/non_existent_job_xyz/cancel")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")

    data = resp.json()
    assert data["status"] == 404
    assert "https://hustler.local/errors/404" in data["type"]
    assert "bulunamadı" in data["detail"].lower() or "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_already_terminal_job_returns_rfc7807_conflict(
    client: AsyncClient, test_env: tuple[JobRepository, EventBroker]
) -> None:
    repo, _ = test_env
    job_id = await repo.create()
    await repo.update(job_id, JobStatus.COMPLETED, 100, output_path="out.mp4")

    resp = await client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")

    data = resp.json()
    assert data["status"] == 409
    assert "https://hustler.local/errors/409" in data["type"]
    assert "sonlanmış" in data["detail"].lower() or "iptal" in data["detail"].lower()
