"""K-806: yt-dlp Kanarya Sondası ve Kırılmaz Keşif Hattı Testleri."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from services.core.hustler.api.routes import discovery as discovery_route
from services.core.hustler.api.routes.discovery import router
from services.core.hustler.db import Database
from services.core.hustler.discovery.canary import (
    DEFAULT_CANARY_URL,
    CanaryReport,
    CanaryStatus,
    ChecksumMismatchError,
    UpdatePolicy,
    _resolve_ytdlp_cmd,
    _WIN32_NO_WINDOW,
    run_ytdlp_canary,
    validate_extractor_payload,
)
from services.core.hustler.discovery.service import (
    DEGRADED_WARNING_MSG,
    ResilientDiscoveryService,
    fallback_discovery,
    generate_deterministic_fallback,
    query_youtube_cache_for_topic,
)


def test_canary_frozen_environment_does_not_spawn_sys_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """PyInstaller dondurulmuş ortamında (sys.frozen=True) sys.executable asla döndürülmemeli."""
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    res = _resolve_ytdlp_cmd()
    assert res is None


def test_canary_report_not_awaitable() -> None:
    """CanaryReport BaseModel nesnesinde __await__ hilesi olmamalıdır."""
    report = CanaryReport(status=CanaryStatus.HEALTHY)
    assert not hasattr(report, "__await__")


def test_canary_reference_url_and_windows_flag() -> None:
    """Referans URL 'Me at the zoo' videosu olmalı ve creationflags belirlenmiş olmalıdır."""
    assert DEFAULT_CANARY_URL == "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    assert isinstance(_WIN32_NO_WINDOW, int)


def test_scenario_2_schema_mismatch_on_malformed_json_or_missing_fields() -> None:
    """Senaryo 2: Bozuk JSON veya eksik şema (id/title/duration yok) SCHEMA_MISMATCH döndürmeli."""
    # 1. Saf şema fonksiyonu kontrolleri
    assert validate_extractor_payload(None) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({}) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({"duration": 10}) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({"id": "vid1"}) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({"id": "vid1", "title": ""}) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({"id": "vid1", "title": "Test", "duration": 0, "webpage_url": ""}) == CanaryStatus.SCHEMA_MISMATCH
    assert validate_extractor_payload({"id": "vid1", "title": "Test", "duration": 12}) == CanaryStatus.HEALTHY
    assert validate_extractor_payload({"id": "vid1", "title": "Test", "webpage_url": "https://youtube.com/..."}) == CanaryStatus.HEALTHY

    # 2. Sonda düzeyinde bozuk JSON simülasyonu
    mock_proc_ok = MagicMock()
    mock_proc_ok.returncode = 0
    mock_proc_ok.stdout = "2026.08.19"
    mock_proc_ok.stderr = ""

    mock_proc_broken = MagicMock()
    mock_proc_broken.returncode = 0
    mock_proc_broken.stdout = "{this is not valid json; broken"
    mock_proc_broken.stderr = ""

    with (
        patch("services.core.hustler.discovery.canary._resolve_ytdlp_cmd", return_value=["yt-dlp"]),
        patch("subprocess.run", side_effect=[mock_proc_ok, mock_proc_broken]),
    ):
        rep = run_ytdlp_canary(timeout_sec=1.0)
        assert rep.status == CanaryStatus.SCHEMA_MISMATCH
        assert rep.error_detail is not None
        assert "JSON ayrıştırma hatası" in rep.error_detail


def test_scenario_3_wrong_sha256_raises_and_preserves_target_binary() -> None:
    """Senaryo 3: Yanlış SHA-256 hash verildiğinde ChecksumMismatchError fırlatılmalı ve hedef binary ezilmemelidir."""
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "bin" / "yt-dlp.exe"
        target.parent.mkdir(parents=True, exist_ok=True)
        original_data = b"ORIGINAL_STABLE_BINARY_V1"
        target.write_bytes(original_data)

        stage = Path(td) / "stage.bin"
        poisoned_data = b"POISONED_CORRUPTED_BINARY"
        stage.write_bytes(poisoned_data)

        # Yanlış hash veriyoruz
        fake_expected_hash = hashlib.sha256(b"SOME_OTHER_DATA").hexdigest()
        with pytest.raises(ChecksumMismatchError):
            UpdatePolicy.apply_verified_binary_update(stage, target, fake_expected_hash)

        # Hedef binary kesinlikle ezilmemiş ve korunmuş olmalı
        assert target.exists()
        assert target.read_bytes() == original_data

        # Doğru hash ile atomik olarak ezilmeli
        valid_hash = hashlib.sha256(poisoned_data).hexdigest()
        res_path = UpdatePolicy.apply_verified_binary_update(stage, target, valid_hash)
        assert res_path == target
        assert target.read_bytes() == poisoned_data


def test_scenario_1_canary_handles_subprocess_crash_and_timeout() -> None:
    """Senaryo 1: yt-dlp çıkarıcısı çöktüğünde (returncode != 0 veya TimeoutExpired) kanarya DEGRADED_EXTRACTOR_BROKEN dönmeli."""
    mock_proc_ver = MagicMock()
    mock_proc_ver.returncode = 0
    mock_proc_ver.stdout = "2026.08.19"
    mock_proc_ver.stderr = ""

    # 1. returncode != 0 (ExtractorError / Çökme)
    mock_proc_err = MagicMock()
    mock_proc_err.returncode = 1
    mock_proc_err.stdout = ""
    mock_proc_err.stderr = "ERROR: [youtube] Signature extraction failed"

    with (
        patch("services.core.hustler.discovery.canary._resolve_ytdlp_cmd", return_value=["yt-dlp"]),
        patch("subprocess.run", side_effect=[mock_proc_ver, mock_proc_err]),
    ):
        rep = run_ytdlp_canary(timeout_sec=1.0)
        assert rep.status == CanaryStatus.DEGRADED_EXTRACTOR_BROKEN
        assert rep.error_detail is not None
        assert "Signature extraction failed" in rep.error_detail

    # 2. TimeoutExpired
    with (
        patch("services.core.hustler.discovery.canary._resolve_ytdlp_cmd", return_value=["yt-dlp"]),
        patch("subprocess.run", side_effect=[mock_proc_ver, subprocess.TimeoutExpired(cmd=["yt-dlp"], timeout=1.0)]),
    ):
        rep_timeout = run_ytdlp_canary(timeout_sec=1.0)
        assert rep_timeout.status == CanaryStatus.DEGRADED_EXTRACTOR_BROKEN
        assert rep_timeout.error_detail is not None
        assert "zaman aşımı" in rep_timeout.error_detail


def test_deterministic_fallback_ideas() -> None:
    """Deterministik fallback fikir üretimi."""
    topic = "Kripto Para"
    ideas1 = generate_deterministic_fallback(topic)
    ideas2 = generate_deterministic_fallback(topic)
    assert len(ideas1) == 5
    assert ideas1 == ideas2
    assert all(topic in str(it["title"]) for it in ideas1)
    assert all(float(str(it["score"])) >= 50.0 for it in ideas1)


async def test_fallback_discovery_uses_cache_or_template(db: Database) -> None:
    """Önbellekte veri varsa önbellekten, yoksa şablondan degraded kurtarma yapılmalıdır."""
    empty_res = await fallback_discovery(db, "Yapay Zeka")
    assert empty_res["degraded"] is True
    assert empty_res["warning"] == DEGRADED_WARNING_MSG
    assert isinstance(empty_res["results"], list)
    assert len(empty_res["results"]) == 5

    cache_payload = {
        "items": [
            {
                "id": {"videoId": "cached_vid_1"},
                "snippet": {"title": "Yapay Zeka Geleceği"},
            }
        ]
    }
    await db.execute_write("""
        CREATE TABLE IF NOT EXISTS youtube_cache (
            cache_key TEXT PRIMARY KEY,
            response_json TEXT,
            created_at REAL
        )
    """)
    await db.execute_write(
        "INSERT INTO youtube_cache (cache_key, response_json, created_at) VALUES (?, ?, 1000.0)",
        ("https://www.googleapis.com/youtube/v3/search?q=yapay+zeka", json.dumps(cache_payload)),
    )
    await db.trigger_maintenance()

    cached_items = await query_youtube_cache_for_topic(db, "yapay zeka")
    assert len(cached_items) >= 1
    assert cached_items[0]["video_id"] == "cached_vid_1"

    cached_res = await fallback_discovery(db, "yapay zeka")
    assert cached_res["degraded"] is True
    assert cached_res["warning"] == DEGRADED_WARNING_MSG
    assert isinstance(cached_res["results"], list)
    first_res = cached_res["results"][0]
    assert isinstance(first_res, dict)
    assert first_res["video_id"] == "cached_vid_1"


async def test_resilient_discovery_service_integration(db: Database) -> None:
    """ResilientDiscoveryService: Çıkarıcı çöktüğünde graceful degradation ile kurtarmalıdır."""
    service = ResilientDiscoveryService(db)

    async def _failing_orchestrator() -> dict[str, object]:
        raise subprocess.SubprocessError("yt-dlp process failure")

    res = await service.run_resilient_discovery("Siber Güvenlik", orchestrator_call=_failing_orchestrator)
    assert res["degraded"] is True
    assert res["warning"] == DEGRADED_WARNING_MSG
    assert isinstance(res["results"], list)
    assert len(res["results"]) == 5


async def test_api_route_graceful_degradation_on_exception(db: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    """API rotası, yt-dlp/orkestratör çöktüğünde 500 dönmemeli, 200 + degraded: True dönmelidir."""
    TOKEN = "canary-token"
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-looking-key")

    class CrashingOrchestrator:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def init_tables(self) -> None:
            pass

        async def run_discovery(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("yt-dlp ExtractorError simülasyonu!")

    class DummyClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> DummyClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.session_token = TOKEN
    app.state.db = db
    app.state.cache = object()

    transport = httpx.ASGITransport(app=app)
    with (
        patch.object(discovery_route, "YouTubeClient", DummyClient),
        patch.object(discovery_route, "DiscoveryOrchestrator", CrashingOrchestrator),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/discovery/run",
                json={"topic": "Biyoteknoloji", "max_results": 20, "score_threshold": 30.0},
                headers={"Authorization": f"Bearer {TOKEN}"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["degraded"] is True
    assert data["warning"] == DEGRADED_WARNING_MSG
    assert len(data["results"]) == 5
    assert all("Biyoteknoloji" in it["title"] for it in data["results"])
