import pytest
from httpx import ASGITransport, AsyncClient
from services.core.hustler.main import app, SESSION_TOKEN

@pytest.mark.asyncio
async def test_pipeline_unauthorized() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/pipeline/script", json={"idea_id": "1", "topic": "t", "title": "tt"})
        assert resp.status_code == 401
        assert resp.headers.get("content-type") == "application/problem+json"

@pytest.mark.asyncio
async def test_pipeline_generate_script() -> None:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pipeline/script",
            headers=headers,
            json={"idea_id": "idea_1", "topic": "Yapay Zeka", "title": "Geleceğin Teknolojisi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "script_id" in data
        assert data["title"] == "Geleceğin Teknolojisi"
        assert len(data["scenes"]) == 3
        assert data["is_approved"] is False

@pytest.mark.asyncio
async def test_pipeline_generate_audio() -> None:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pipeline/audio",
            headers=headers,
            json={"script_id": "scr_1", "voice_id": "tr-TR", "text": "Bu bir test seslendirme metnidir."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_generated"] is True
        assert data["duration_seconds"] > 0

@pytest.mark.asyncio
async def test_pipeline_prepare_assets() -> None:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pipeline/assets",
            headers=headers,
            json={"script_id": "scr_1", "slots": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["slots"]) >= 3
        assert data["all_slots_filled"] is True

@pytest.mark.asyncio
async def test_pipeline_preview() -> None:
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pipeline/preview",
            headers=headers,
            json={"script_id": "scr_1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "preview_url" in data
        assert data["is_verified"] is True
