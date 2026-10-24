import pytest
import pytest_asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from fastapi import FastAPI
import httpx

from services.core.hustler.api.routes.channels import router as channels_router
from services.core.hustler.api.routes.discovery import router as discovery_router
from services.core.hustler.api.routes.pipeline import router as pipeline_router
from services.core.hustler.db import Database
from services.core.hustler.storage.cache import YouTubeCache
from services.core.hustler.storage.channels import ChannelRepository
from services.core.hustler.storage.scripts import ScriptRepository

TOKEN = "test-token-channels"


@pytest_asyncio.fixture
async def temp_db(tmp_path: Path) -> AsyncIterator[Database]:
    db_file = tmp_path / "test_channels.db"
    db = Database(db_file)
    await db.init()
    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def channel_repo(temp_db: Database) -> ChannelRepository:
    repo = ChannelRepository(temp_db)
    await repo.init_table()
    return repo


@pytest.mark.asyncio
async def test_channel_repository_crud(channel_repo: ChannelRepository) -> None:
    # 1. Create channel
    chan = await channel_repo.create(
        name="Tarih & Gizem Shorts",
        channel_url="https://youtube.com/@tarihgizem",
        description="Kadim sırlar ve belgesel kurguları",
    )
    assert chan.id.startswith("chn_")
    assert chan.name == "Tarih & Gizem Shorts"
    assert chan.channel_url == "https://youtube.com/@tarihgizem"
    assert chan.created_at > 0

    # 2. Get by ID
    fetched = await channel_repo.get_by_id(chan.id)
    assert fetched is not None
    assert fetched.id == chan.id
    assert fetched.name == "Tarih & Gizem Shorts"

    # 3. List all
    chan2 = await channel_repo.create(
        name="Finans Analiz",
        channel_url="https://youtube.com/@finansanaliz",
        description="Günlük borsa ve makroekonomi",
    )
    all_channels = await channel_repo.list_all()
    assert len(all_channels) == 2
    assert all_channels[0].id == chan2.id  # Ordered by created_at DESC

    # 4. Delete
    deleted = await channel_repo.delete(chan.id)
    assert deleted is True

    # 5. Verify deleted
    assert await channel_repo.get_by_id(chan.id) is None
    assert await channel_repo.delete(chan.id) is False
    remaining = await channel_repo.list_all()
    assert len(remaining) == 1
    assert remaining[0].id == chan2.id


@pytest.mark.asyncio
async def test_channel_api_routes(temp_db: Database, channel_repo: ChannelRepository) -> None:
    app = FastAPI()
    app.state.session_token = TOKEN
    app.state.db = temp_db
    app.state.channel_repo = channel_repo
    app.include_router(channels_router, prefix="/api/v1")

    headers = {"Authorization": f"Bearer {TOKEN}"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Unauthorized access (no token) -> 401
        res = await client.get("/api/v1/channels")
        assert res.status_code == 401

        # 2. List empty channels
        res = await client.get("/api/v1/channels", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

        # 3. Create channel -> 201
        payload = {
            "name": "Bilim & Teknoloji",
            "channel_url": "https://youtube.com/@bilimtek",
            "description": "Yapay zeka ve kuantum fiziği",
        }
        res = await client.post("/api/v1/channels", json=payload, headers=headers)
        assert res.status_code == 201
        created = res.json()
        assert created["id"].startswith("chn_")
        assert created["name"] == "Bilim & Teknoloji"
        assert created["metrics"]["total_scripts"] == 0

        chan_id = created["id"]

        # 4. Get channel detail -> 200
        res = await client.get(f"/api/v1/channels/{chan_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["id"] == chan_id

        # 5. Get non-existent channel -> 404
        res = await client.get("/api/v1/channels/non_existent_id", headers=headers)
        assert res.status_code == 404

        # 6. Delete channel -> 200
        res = await client.delete(f"/api/v1/channels/{chan_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

        # 7. Delete again -> 404
        res = await client.delete(f"/api/v1/channels/{chan_id}", headers=headers)
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Faz 2/2: Gerçek Metrikler, Güvenli Göç ve Akış Köprüsü
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_channel_real_metrics_from_sqlite(
    temp_db: Database, channel_repo: ChannelRepository
) -> None:
    chan = await channel_repo.create("Uzay Bilimi", "https://youtube.com/@uzay", "Astrofizik")
    other = await channel_repo.create("Finans", "https://youtube.com/@finans", "Makro")

    linked = await channel_repo.record_research(
        chan.id,
        "kara delik",
        [
            {"video_id": "v1", "title": "A", "score": 90.0},
            {"video_id": "v2", "title": "B", "score": 80.0},
            {"id": "v3", "title": "C", "score": 70},
            {"title": "kimliksiz — atlanır"},
        ],
    )
    assert linked == 3

    scripts = ScriptRepository(temp_db)
    await scripts.save("scr_a", "Senaryo A", "Metin A uzun içerik", channel_id=chan.id)
    await scripts.save("scr_b", "Senaryo B", "Metin B uzun içerik", channel_id=chan.id)
    await scripts.save("scr_free", "Kanalsız", "Bağımsız senaryo")
    # Kanal belirtilmeden yeniden kaydetme mevcut kanal bağını korumalı (COALESCE)
    await scripts.save("scr_a", "Senaryo A v2", "Metin A güncellendi")

    metrics = await channel_repo.get_metrics(chan.id)
    assert metrics["total_scripts"] == 2
    assert metrics["total_research"] == 3
    assert metrics["avg_viral_score"] == pytest.approx(80.0)

    other_metrics = await channel_repo.get_metrics(other.id)
    assert other_metrics == {"total_scripts": 0, "total_research": 0, "avg_viral_score": 0.0}

    listed = {c.id: m for c, m in await channel_repo.list_all_with_metrics()}
    assert listed[chan.id]["total_scripts"] == 2
    assert listed[other.id]["total_research"] == 0

    # Kanal silinince bağlı kayıtlar korunur, yalnızca bağ çözülür
    assert await channel_repo.delete(chan.id) is True
    assert await scripts.get("scr_a") is not None
    assert (await channel_repo.get_metrics(chan.id))["total_scripts"] == 0


@pytest.mark.asyncio
async def test_channel_column_safe_migration_on_legacy_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "legacy.db")
    await db.init()
    try:
        # Eski şema: channel_id kolonu olmayan tablolar
        await db.execute_write(
            "CREATE TABLE scripts (script_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "full_text TEXT NOT NULL, scenes_json TEXT NOT NULL DEFAULT '[]', "
            "claims_json TEXT NOT NULL DEFAULT '[]', is_approved INTEGER NOT NULL DEFAULT 0, "
            "content_hash TEXT NOT NULL, updated_at REAL NOT NULL)"
        )
        await db.execute_write(
            "CREATE TABLE discovery_videos (video_id TEXT PRIMARY KEY, title TEXT, "
            "topic TEXT, score REAL, discovered_at REAL)"
        )
        repo = ChannelRepository(db)
        await repo.init_table()
        await repo.init_table()  # idempotent: ikinci çalıştırma hata vermemeli

        for table in ("scripts", "discovery_videos"):
            cols = await repo._table_columns(table)
            assert cols is not None and "channel_id" in cols
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_discovery_and_script_routes_link_channel(
    temp_db: Database, channel_repo: ChannelRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    cache = YouTubeCache(temp_db, ttl_seconds=3600)
    await cache.init_tables()

    app = FastAPI()
    app.state.session_token = TOKEN
    app.state.db = temp_db
    app.state.cache = cache
    app.state.channel_repo = channel_repo
    app.include_router(channels_router, prefix="/api/v1")
    app.include_router(discovery_router, prefix="/api/v1")
    app.include_router(pipeline_router, prefix="/api/v1")
    headers = {"Authorization": f"Bearer {TOKEN}"}

    chan = await channel_repo.create("Tarih", "https://youtube.com/@tarih", "Antik")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/discovery/run",
            json={"topic": "Göbeklitepe", "channel_id": chan.id},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["channel_id"] == chan.id
        assert body["linked_to_channel"] == len(body["results"]) > 0

        first = body["results"][0]
        res = await client.post(
            "/api/v1/pipeline/script",
            json={
                "idea_id": first["video_id"],
                "topic": "Göbeklitepe",
                "title": first["title"],
                "channel_id": chan.id,
            },
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["channel_id"] == chan.id

        res = await client.get(f"/api/v1/channels/{chan.id}", headers=headers)
        metrics = res.json()["metrics"]
        assert metrics["total_research"] == len(body["results"])
        assert metrics["total_scripts"] == 1
        assert metrics["avg_viral_score"] > 0

        # Kanal belirtilmeyen keşif hâlâ API anahtarı ister (geriye dönük sözleşme)
        res = await client.post(
            "/api/v1/discovery/run", json={"topic": "Göbeklitepe"}, headers=headers
        )
        assert res.status_code == 500


@pytest.mark.asyncio
async def test_channel_live_stats_endpoint(
    temp_db: Database, channel_repo: ChannelRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = FastAPI()
    app.state.session_token = TOKEN
    app.state.db = temp_db
    app.state.channel_repo = channel_repo
    app.include_router(channels_router, prefix="/api/v1")
    headers = {"Authorization": f"Bearer {TOKEN}"}

    chan = await channel_repo.create("Test Kanal", "https://youtube.com/@test", "Açıklama")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        async def mock_extract(url: str, force_refresh: bool = False) -> dict[str, object]:
            return {
                "channel_name": "Test Kanal",
                "subscribers": 100000,
                "subscribers_formatted": "100.0K",
                "videos": [{"id": "v1", "title": "Vid 1", "view_count": 5000}],
                "shorts": [{"id": "s1", "title": "Short 1", "view_count": 12000}],
                "is_live": True,
            }
        monkeypatch.setattr("services.core.hustler.api.routes.channels.fetch_channel_live_stats", mock_extract)

        res = await client.get(f"/api/v1/channels/{chan.id}/live-stats", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["channel_id"] == chan.id
        assert data["live_data"]["subscribers"] == 100000
        assert len(data["live_data"]["videos"]) == 1
        assert len(data["live_data"]["shorts"]) == 1


def test_channel_analytics_pandas_numpy() -> None:
    from services.core.hustler.services.channel_analytics import compute_channel_analytics

    sample_videos = [
        {"id": "v1", "title": "Büyük Piramit Gizemi", "view_count": 50000, "duration": 120},
        {"id": "v2", "title": "Mars Kolonisi", "view_count": 80000, "duration": 300},
        {"id": "v3", "title": "Kuantum Fiziği 101", "view_count": 120000, "duration": 450},
    ]
    sample_shorts = [
        {"id": "s1", "title": "Hızlı Bilgi #1", "view_count": 25000, "duration": 45},
        {"id": "s2", "title": "Hızlı Bilgi #2", "view_count": 45000, "duration": 50},
    ]

    analytics = compute_channel_analytics(sample_videos, sample_shorts)
    assert analytics["has_data"] is True

    # 1. Çizgi Grafiği (Line Chart) kontrolleri
    line = analytics["line_chart"]
    assert isinstance(line, dict)
    pts = line["points"]
    assert isinstance(pts, list)
    assert len(pts) == 5
    assert line["max_val"] == 120000
    assert line["min_val"] == 25000
    assert line["trend_direction"] in ("up", "down", "stable")
    pt0 = pts[0]
    assert isinstance(pt0, dict)
    assert pt0["view_count"] == 50000
    assert "rolling_avg" in pt0

    # 2. Daire Grafiği (Pie Chart) kontrolleri
    pie = analytics["pie_chart"]
    assert isinstance(pie, dict)
    assert pie["total_views"] == 50000 + 80000 + 120000 + 25000 + 45000
    slices = pie["slices"]
    assert isinstance(slices, list)
    assert len(slices) == 2  # Video & Short
    total_pct = sum(float(str(s["percentage"])) for s in slices if isinstance(s, dict))
    assert 99.0 <= total_pct <= 101.0  # Yuvarlama payı

    # 4. Ayrı Uzun Video ve Shorts Çizgi Grafiği Kontrolleri
    vid_line = analytics["videos_line_chart"]
    assert isinstance(vid_line, dict)
    vid_pts = vid_line["points"]
    assert isinstance(vid_pts, list)
    assert len(vid_pts) == 3
    assert vid_line["max_val"] == 120000
    assert vid_line["min_val"] == 50000
    assert vid_line["trend_direction"] in ("up", "down", "stable")

    short_line = analytics["shorts_line_chart"]
    assert isinstance(short_line, dict)
    short_pts = short_line["points"]
    assert isinstance(short_pts, list)
    assert len(short_pts) == 2
    assert short_line["max_val"] == 45000
    assert short_line["min_val"] == 25000
    assert short_line["trend_direction"] in ("up", "down", "stable")


def test_infer_channel_niche_query_from_real_videos() -> None:
    from services.core.hustler.services.channel_stats import infer_channel_niche_query

    videos: list[dict[str, object]] = [
        {"title": "Kuantum Bilgisayarlar ve Yapay Zeka Geleceği", "view_count": 500000},
        {"title": "Kuantum Fiziği Neden Her Şeyi Değiştiriyor?", "view_count": 320000},
    ]
    shorts: list[dict[str, object]] = [
        {"title": "Yapay Zeka ve Kuantum Çipleri", "view_count": 850000},
    ]
    q = infer_channel_niche_query("Bilim Kanalı", "Kuantum ve yapay zeka", videos, shorts)
    assert "kuantum" in q
    assert "yapay" in q or "zeka" in q



