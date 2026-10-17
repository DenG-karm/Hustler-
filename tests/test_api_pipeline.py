import pytest
from httpx import ASGITransport, AsyncClient
from services.core.hustler.db import Database
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


@pytest.mark.asyncio
async def test_pipeline_save_script_idempotent(db: Database) -> None:
    from services.core.hustler.storage.scripts import ScriptRepository

    repo = ScriptRepository(db)
    await repo.init_table()
    app.state.db = db
    app.state.script_repo = repo

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    payload = {
        "script_id": "scr_test_100",
        "title": "İdempotent Senaryo",
        "full_text": "Bu senaryo veritabanına kaydedilecek ve idempotency test edilecektir.",
        "scenes": [{"order": 1, "narration": "Giriş", "visual_prompt": "Prompt 1"}],
        "claims": [{"id": "c1", "text": "İddia 1", "verified": True}],
        "is_approved": True,
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. İlk kayıt: SAVED dönmeli
        resp1 = await client.post("/api/v1/pipeline/script/save", headers=headers, json=payload)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "SAVED"
        assert data1["is_idempotent"] is True
        assert "content_hash" in data1
        assert "updated_at" in data1

        # 2. İkinci kayıt (birebir aynı payload): UNCHANGED dönmeli, hash ve updated_at aynı kalmalı
        resp2 = await client.post("/api/v1/pipeline/script/save", headers=headers, json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "UNCHANGED"
        assert data2["is_idempotent"] is True
        assert data2["content_hash"] == data1["content_hash"]
        assert data2["updated_at"] == data1["updated_at"]

        # 3. İçerik değiştiğinde: Tekrar SAVED dönmeli ve yeni hash üretilmeli
        modified_payload = dict(payload)
        modified_payload["full_text"] = "Değiştirilmiş senaryo metni burada yer almaktadır ve uzundur."
        resp3 = await client.post("/api/v1/pipeline/script/save", headers=headers, json=modified_payload)
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["status"] == "SAVED"
        assert data3["content_hash"] != data1["content_hash"]
        assert data3["updated_at"] >= data1["updated_at"]


@pytest.mark.asyncio
async def test_pipeline_pydantic_validation_and_real_engine_outputs() -> None:
    from pathlib import Path
    import wave

    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Boş alan gönderildiğinde Pydantic BaseModel doğrulaması 422 dönmeli
        bad_resp = await client.post(
            "/api/v1/pipeline/script",
            headers=headers,
            json={"idea_id": "", "topic": "", "title": ""},
        )
        assert bad_resp.status_code == 422

        # Audio uç noktası gerçek okunabilir PCM WAV ve .ass altyazı üretmeli
        audio_resp = await client.post(
            "/api/v1/pipeline/audio",
            headers=headers,
            json={"script_id": "scr_real_test", "voice_id": "tr-TR", "text": "Gerçek kelime hizalama ve ses testi."},
        )
        assert audio_resp.status_code == 200
        audio_data = audio_resp.json()
        wav_path = Path(audio_data["audio_path"])
        ass_path = Path(audio_data["ass_path"])
        assert wav_path.is_file() and wav_path.stat().st_size > 44
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0
        assert ass_path.is_file()
        assert "[Events]" in ass_path.read_text(encoding="utf-8")
        assert audio_data["word_count"] == 6


