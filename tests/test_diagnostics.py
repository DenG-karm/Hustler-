"""
K-803 (Faz 1 & 2): Doctor Motoru, Redaction ve Tanılama Zip Paketi Test Paketi.
- API anahtarlarının (sk-..., xi-..., Bearer...) ve ortam değişkenlerinin maskelenmesi.
- Windows/macOS/Linux kullanıcı dizinlerinin (<REDACTED>) maskelenmesi.
- DoctorReport Pydantic modelinin alan doğrulaması, SQLite quick_check ve status kararları.
- hustler_diag_<timestamp>.zip üretim doğrulaması ve zip içeriği.
- Medya (.mp4, .mp3, .wav) ve ham SQLite veritabanı dışlama kuralı.
- /api/v1/diagnostics/export API uç noktası yetki ve dosya indirme testleri.
"""

from __future__ import annotations

import json
from pathlib import Path
import zipfile
from collections.abc import AsyncIterator
import httpx
import pytest

from services.core.hustler.db import Database
from services.core.hustler.diagnostics.bundler import (
    FORBIDDEN_EXTENSIONS,
    async_create_diagnostics_bundle,
    create_diagnostics_bundle,
)
from services.core.hustler.diagnostics.doctor import (
    DoctorReport,
    async_run_system_doctor,
    run_system_doctor,
)
from services.core.hustler.diagnostics.redactor import redact_sensitive_text
from services.core.hustler.main import SESSION_TOKEN, app
from services.core.hustler.storage.sessions import ProjectSessionRepository


def test_redact_sensitive_text_masks_api_keys_and_tokens() -> None:
    # 1. Bearer Token
    raw_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz123"
    redacted = redact_sensitive_text(raw_bearer)
    assert "Bearer [REDACTED]" in redacted
    assert "eyJhbGci" not in redacted

    # 2. OpenAI sk-...
    raw_openai = "Connecting with key sk-proj-1234567890abcdef1234567890 to endpoint"
    redacted = redact_sensitive_text(raw_openai)
    assert "[REDACTED]" in redacted
    assert "sk-proj-1234567890abcdef1234567890" not in redacted

    # 3. ElevenLabs xi-...
    raw_eleven = "ElevenLabs xi-9876543210fedcba9876543210 voice worker"
    redacted = redact_sensitive_text(raw_eleven)
    assert "[REDACTED]" in redacted
    assert "xi-9876543210fedcba9876543210" not in redacted

    # 4. Ortam Değişkeni / Yapılandırma Formatı
    raw_env = 'ELEVENLABS_API_KEY="my_secret_token_123" and OPENAI_API_KEY=sk-abc1234567890123'  # gitleaks:allow
    redacted = redact_sensitive_text(raw_env)
    assert 'ELEVENLABS_API_KEY="[REDACTED]"' in redacted
    assert "OPENAI_API_KEY=[REDACTED]" in redacted
    assert "my_secret_token_123" not in redacted

    # 5. Bozuk veya tek/çift tırnaklı loglarda kapanış tırnağı koruması (JSON log formatı bozulmaz)
    malformed_env = 'Config log: API_KEY=12345" and OTHER_API_KEY=\'secret123\' and OPENAI_API_KEY="sk-live"'
    redacted_malformed = redact_sensitive_text(malformed_env)
    assert 'API_KEY=[REDACTED]"' in redacted_malformed
    assert "OTHER_API_KEY='[REDACTED]'" in redacted_malformed
    assert 'OPENAI_API_KEY="[REDACTED]"' in redacted_malformed


def test_redact_sensitive_text_masks_user_directories() -> None:
    # 1. Windows Standart Yol
    win_path = r"Log file at C:\Users\Deniz\AppData\Local\Hustler\app.log"
    redacted = redact_sensitive_text(win_path)
    assert r"Log file at C:\Users\<REDACTED>\AppData\Local\Hustler\app.log" == redacted

    # 2. Windows JSON Serialized (Çift Ters Bölü)
    win_json = r'{"path": "C:\\Users\\Deniz\\pushToUp\\Hustler"}'
    redacted = redact_sensitive_text(win_json)
    assert r'{"path": "C:\\Users\\<REDACTED>\\pushToUp\\Hustler"}' == redacted

    # 3. macOS / Unix /Users/
    mac_path = "/Users/Deniz/Library/Application Support/Hustler/data.db"
    redacted = redact_sensitive_text(mac_path)
    assert "/Users/<REDACTED>/Library/Application Support/Hustler/data.db" == redacted

    # 4. Linux /home/
    linux_path = "/home/deniz/.config/hustler/settings.json"
    redacted = redact_sensitive_text(linux_path)
    assert "/home/<REDACTED>/.config/hustler/settings.json" == redacted

    # 5. Boşluklu Windows Kullanıcı Adı (Örn: Ad Soyad)
    win_spaced = r"C:\Users\Ad Soyad\AppData\Local\Hustler\app.log"
    redacted_spaced = redact_sensitive_text(win_spaced)
    assert r"C:\Users\<REDACTED>\AppData\Local\Hustler\app.log" == redacted_spaced

    # 6. Boşluklu Windows JSON Kaçışlı Yol
    win_json_spaced = r'{"path": "C:\\Users\\Ad Soyad\\AppData"}'
    assert r'{"path": "C:\\Users\\<REDACTED>\\AppData"}' == redact_sensitive_text(win_json_spaced)


def test_redact_sensitive_text_handles_edge_cases() -> None:
    assert redact_sensitive_text("") == ""
    normal_text = "Standard log message with no secrets or paths."
    assert redact_sensitive_text(normal_text) == normal_text


@pytest.mark.asyncio
async def test_run_system_doctor_returns_valid_report(db: Database) -> None:
    # 1. Senkron çağrı
    report = run_system_doctor(db)
    assert isinstance(report, DoctorReport)
    assert len(report.python_version) > 0
    assert len(report.sqlite_version) > 0
    assert isinstance(report.ffmpeg_available, bool)
    assert isinstance(report.ytdlp_available, bool)
    assert report.yt_dlp_available == report.ytdlp_available
    assert report.disk_free_mb > 0
    assert report.db_quick_check == "ok"
    assert report.status in ("HEALTHY", "DEGRADED", "CRITICAL")

    # 2. Awaitable çağrı (aynı nesne await edilebilir)
    report_await = await run_system_doctor(db)
    assert report_await.status == report.status

    # 3. Asenkron sarmalayıcı çağrı
    report_async = await async_run_system_doctor(db)
    assert report_async.status == report.status


@pytest.mark.asyncio
async def test_run_system_doctor_detects_corrupted_database(
    tmp_path: Path,
) -> None:
    bad_db_file = tmp_path / "corrupted_doctor.sqlite3"
    with open(bad_db_file, "wb") as f:
        f.write(b"NOT A VALID SQLITE DATABASE FILE HEADER JUNK DATA")

    bad_db = Database(bad_db_file)
    report = run_system_doctor(bad_db)

    assert report.status == "CRITICAL"
    assert report.db_quick_check != "ok"


def test_run_system_doctor_handles_missing_tools(
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_which(cmd: str) -> str | None:
        return None

    import shutil
    monkeypatch.setattr(shutil, "which", mock_which)

    report = run_system_doctor(db)
    assert report.ffmpeg_available is False
    assert report.ytdlp_available is False
    assert report.ffmpeg_version is None
    assert report.ytdlp_version is None
    assert report.status in ("DEGRADED", "CRITICAL")


@pytest.mark.asyncio
async def test_create_diagnostics_bundle_creates_valid_zip_with_all_sections(
    db: Database,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "diag_out"
    custom_log = tmp_path / "test_app.log"
    custom_log.write_text(
        "2026-10-14T12:00:00Z [INFO] Service started.\n"
        "2026-10-14T12:01:00Z [DEBUG] Cache cleared.\n",
        encoding="utf-8",
    )

    bundle_path = await async_create_diagnostics_bundle(output_dir, db, log_path=custom_log)

    assert bundle_path.exists()
    assert bundle_path.is_file()
    assert bundle_path.name.startswith("hustler_diag_")
    assert bundle_path.name.endswith(".zip")
    assert bundle_path.stat().st_size > 0

    with zipfile.ZipFile(bundle_path, "r") as zf:
        namelist = zf.namelist()
        assert "doctor.json" in namelist
        assert "versions.json" in namelist
        assert "logs/recent.log" in namelist
        assert "session_summary.json" in namelist

        # 1. doctor.json doğrulaması
        doc_raw = zf.read("doctor.json").decode("utf-8")
        doc_data = json.loads(doc_raw)
        assert "status" in doc_data
        assert "db_quick_check" in doc_data
        assert doc_data["db_quick_check"] == "ok"

        # 2. versions.json doğrulaması
        ver_raw = zf.read("versions.json").decode("utf-8")
        ver_data = json.loads(ver_raw)
        assert "app_version" in ver_data
        assert "python_version" in ver_data
        assert "sqlite_version" in ver_data

        # 3. logs/recent.log doğrulaması
        log_content = zf.read("logs/recent.log").decode("utf-8")
        assert "Service started" in log_content

        # 4. session_summary.json doğrulaması
        session_raw = zf.read("session_summary.json").decode("utf-8")
        session_data = json.loads(session_raw)
        assert "active_session" in session_data


@pytest.mark.asyncio
async def test_diagnostics_bundle_strictly_forbids_media_and_raw_database_files(
    db: Database,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "diag_out_forbidden"
    bundle_path = create_diagnostics_bundle(output_dir, db)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        for name in zf.namelist():
            for forbidden in FORBIDDEN_EXTENSIONS:
                assert not name.lower().endswith(forbidden), (
                    f"MİMARİ KURAL İHLALİ: {name} yasaklı {forbidden} uzantısına sahip!"
                )


@pytest.mark.asyncio
async def test_diagnostics_bundle_excludes_script_text_and_masks_secrets(
    db: Database,
    tmp_path: Path,
) -> None:
    # 1. Aktif oturuma hassas veriler ve uzun metin ekle
    repo = ProjectSessionRepository(db)
    await repo.init_table()
    await repo.save_session(
        session_id="session_diag_test_001",
        topic="C:\\Users\\Deniz\\SecretTopic with sk-proj-1234567890abcdef1234567890",
        current_step="RENDER",
        checkpoint_step="PREVIEW",
        status="RUNNING",
        script={
            "id": "scr_999",
            "title": "Gizli Başlık",
            "full_text": "BU METİN ASLA TANILAMA PAKETİNE DAHİL EDİLMEMELİDİR. 500 kelimelik gizli içerik...",
        },
        audio={"voiceId": "tr-TR-Standard-A", "audioUrl": "http://audio/secret.mp3"},
    )

    # 2. Log dosyasına hassas token yaz
    custom_log = tmp_path / "sensitive.log"
    custom_log.write_text(
        "2026-10-14T12:00:00Z [INFO] Initializing ELEVENLABS_API_KEY=\"xi-1234567890abcdef12345\"\n"
        "2026-10-14T12:01:00Z [DEBUG] User dir: C:\\Users\\Deniz\\AppData\\Roaming\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "diag_out_masked"
    bundle_path = create_diagnostics_bundle(output_dir, db, log_path=custom_log)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        # session_summary.json kontrolü
        session_raw = zf.read("session_summary.json").decode("utf-8")
        assert "BU METİN ASLA TANILAMA PAKETİNE DAHİL EDİLMEMELİDİR" not in session_raw
        assert "sk-proj-1234567890abcdef1234567890" not in session_raw
        assert "[REDACTED]" in session_raw
        assert "<REDACTED>" in session_raw

        # logs/recent.log kontrolü
        log_raw = zf.read("logs/recent.log").decode("utf-8")
        assert "xi-1234567890abcdef12345" not in log_raw
        assert "[REDACTED]" in log_raw
        assert "Deniz" not in log_raw or "<REDACTED>" in log_raw


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    app.state.event_broker = None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.state.event_broker = None


@pytest.mark.asyncio
async def test_diagnostics_export_api_requires_auth_and_returns_valid_bundle(
    api_client: httpx.AsyncClient,
    db: Database,
) -> None:
    # app.state.db'yi ayarla
    app.state.db = db

    # 1. Token olmadan 401 dönmeli
    resp_unauth = await api_client.post("/api/v1/diagnostics/export")
    assert resp_unauth.status_code == 401

    # 2. Yetkili çağrıda (format=json) 200 ve JSON meta verisi dönmeli
    headers = {"Authorization": f"Bearer {SESSION_TOKEN}"}
    resp_json = await api_client.post("/api/v1/diagnostics/export?format=json", headers=headers)
    assert resp_json.status_code == 200
    meta = resp_json.json()
    assert meta["status"] == "ok"
    assert meta["filename"].startswith("hustler_diag_")
    assert meta["filename"].endswith(".zip")
    assert Path(meta["bundle_path"]).exists()

    # 3. Yetkili GET çağrısında dosya akışı (zip) dönmeli
    resp_get = await api_client.get("/api/v1/diagnostics/export", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.headers["content-type"] == "application/zip"
    assert "attachment" in resp_get.headers.get("content-disposition", "")
    assert len(resp_get.content) > 0


@pytest.mark.asyncio
async def test_diagnostics_bundle_redacts_fake_api_key_and_user_secret_file_in_logs(
    db: Database,
    tmp_path: Path,
) -> None:
    """Log dosyasına sahte API anahtarı (sk-live-1234567890abcdef) ve C:\\Users\\Deniz\\secret.txt yazıldığında,

    üretilen .zip içindeki log dosyasında bu ifadelerin kesinlikle bulunmadığı ([REDACTED] olduğu) kanıtlanır.
    """
    fake_log = tmp_path / "app_leak_test.log"
    fake_log.write_text(
        "2026-10-14T14:00:00Z [INFO] Connecting with API key: sk-live-1234567890abcdef\n"
        "2026-10-14T14:01:00Z [DEBUG] Reading secret file from C:\\Users\\Deniz\\secret.txt\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "diag_out_secrets"
    bundle_path = create_diagnostics_bundle(output_dir, db, log_path=fake_log)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        log_content = zf.read("logs/recent.log").decode("utf-8")
        # Kesinlikle bulunmamalı
        assert "sk-live-1234567890abcdef" not in log_content
        assert "C:\\Users\\Deniz\\secret.txt" not in log_content
        # Maskelenmiş formatlar yer almalı
        assert "[REDACTED]" in log_content
        assert "C:\\Users\\<REDACTED>\\secret.txt" in log_content


@pytest.mark.asyncio
async def test_diagnostics_bundle_zip_integrity_and_valid_json_structure(
    db: Database,
    tmp_path: Path,
) -> None:
    """Üretilen .zip dosyasının bozuk olmadığı (zipfile.ZipFile.testzip() is None) ve

    içinde doctor.json ile versions.json'ın geçerli JSON olarak yer aldığı kanıtlanır.
    """
    output_dir = tmp_path / "diag_out_integrity"
    bundle_path = create_diagnostics_bundle(output_dir, db)

    with zipfile.ZipFile(bundle_path, "r") as zf:
        # Zip bozulma testi: testzip() dosya bozuk değilse None döner
        assert zf.testzip() is None

        # doctor.json geçerli JSON mu?
        doctor_str = zf.read("doctor.json").decode("utf-8")
        doctor_obj = json.loads(doctor_str)
        assert isinstance(doctor_obj, dict)
        assert "status" in doctor_obj
        assert "db_quick_check" in doctor_obj
        assert "python_version" in doctor_obj

        # versions.json geçerli JSON mu?
        versions_str = zf.read("versions.json").decode("utf-8")
        versions_obj = json.loads(versions_str)
        assert isinstance(versions_obj, dict)
        assert "app_version" in versions_obj
        assert "sqlite_version" in versions_obj
        assert "schema_version" in versions_obj


@pytest.mark.asyncio
async def test_diagnostics_bundle_size_stays_under_budget_with_50mb_log_or_mp4_present(
    db: Database,
    tmp_path: Path,
) -> None:
    """50 MB'lık sahte bir log veya .mp4 dosyası ortamda dururken,

    üretilen .zip boyutunun bütçeyi (< 5 MB) aşmadığı ve medyanın dışlandığı kanıtlanır.
    """
    # 50 MB'lık sahte log dosyası üret (tail mantığı testi)
    huge_log = tmp_path / "huge_app.log"
    chunk_1mb = (("2026-10-14T14:30:00Z [INFO] " + "A" * 970 + "\n") * 1024).encode("utf-8")
    with open(huge_log, "wb") as f:
        for _ in range(52):  # ~52 MB
            f.write(chunk_1mb)
    assert huge_log.stat().st_size >= 50 * 1024 * 1024

    # Ortamda 50 MB'lık sahte .mp4 dosyası
    fake_video = tmp_path / "huge_render_sample.mp4"
    with open(fake_video, "wb") as f:
        f.truncate(50 * 1024 * 1024)

    output_dir = tmp_path / "diag_out_budget"
    bundle_path = create_diagnostics_bundle(output_dir, db, log_path=huge_log)

    # 1. Zip boyutu kesinlikle 5 MB'ın altında kalmalı (< 500 KB)
    zip_size = bundle_path.stat().st_size
    assert zip_size < 5 * 1024 * 1024
    assert zip_size < 500 * 1024

    # 2. .mp4 dosyasının zip'e KESİNLİKLE sızmadığını doğrula
    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        assert not any(n.endswith(".mp4") for n in names)
        assert "huge_render_sample.mp4" not in names
        # Log dosyasının son maksimum 1000 satırla sınırlandığını doğrula
        log_lines = zf.read("logs/recent.log").decode("utf-8").splitlines()
        assert len(log_lines) <= 1000
