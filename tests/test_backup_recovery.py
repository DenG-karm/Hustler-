"""K-802: SQLite Native Backup API, Önbellek İzolasyonu ve State Rehydration Test Paketi.

Acımasız Testler:
1. Eşzamanlı yazma (concurrent write) sırasında alınan yedeğin tutarlılığı ve bütünlüğü (PRAGMA integrity_check).
2. Önbellek tablolarının (cache_*, %_cache, temp_*) yedekten tamamen arındırılması.
3. Manipüle edilmiş (bozuk byte'lı) yedeğin CorruptedBackupError ile reddedilmesi ve canlı veritabanının korunması.
4. Çökme / kaza sonrası RUNNING veya RENDERING durumunda asılı kalan işlerin kararlı checkpoint adımına kurtarılması.
5. shutil.copy fonksiyonunun KESİNLİKLE kullanılmadığının (monkeypatch kuralı) kanıtı.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import sqlite3

import pytest

from services.core.hustler.db import Database
from services.core.hustler.db.backup import (
    CorruptedBackupError,
    async_create_backup,
    async_restore_backup,
    verify_backup,
)
from services.core.hustler.storage.sessions import (
    ProjectSessionRepository,
)


def _assert_shutil_never_called(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_copy(*args: object, **kwargs: object) -> object:
        raise AssertionError("MİMARİ KURAL İHLALİ: shutil.copy kesinlikle yasaktır!")

    monkeypatch.setattr(shutil, "copy", forbidden_copy)
    monkeypatch.setattr(shutil, "copy2", forbidden_copy)
    monkeypatch.setattr(shutil, "copyfile", forbidden_copy)


@pytest.mark.asyncio
async def test_backup_during_concurrent_writes_is_consistent_and_valid(
    db: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eşzamanlı yazma sırasında alınan SQLite native backup tutarlıdır ve bozulmaz."""
    _assert_shutil_never_called(monkeypatch)

    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS stress_log (id INTEGER PRIMARY KEY, worker_id INT, payload TEXT)"
    )

    is_writing = True

    async def continuous_writer(worker_id: int) -> int:
        count = 0
        while is_writing:
            await db.execute_write(
                "INSERT INTO stress_log (worker_id, payload) VALUES (?, ?)",
                (worker_id, f"worker_{worker_id}_data_{count}"),
            )
            count += 1
            await asyncio.sleep(0.005)
        return count

    # 4 paralel yazıcı başlat
    writers = [asyncio.create_task(continuous_writer(w)) for w in range(4)]

    # Yazıcılar çalışırken biraz veri birikmesini bekle
    await asyncio.sleep(0.05)

    backup_file = tmp_path / "live_concurrent_backup.sqlite3"
    await async_create_backup(db, backup_file)

    # Yazıcıları durdur
    is_writing = False
    await asyncio.gather(*writers)

    # Yedek dosyasını doğrula
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    assert verify_backup(backup_file) is True

    # Yedek içindeki verilerin sağlam olduğunu ve okunduğunu doğrula
    conn = sqlite3.connect(str(backup_file))
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stress_log")
        row = cur.fetchone()
        assert row is not None
        assert row[0] > 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_cache_tables_excluded_from_backup(
    db: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Yedekleme sırasında önbellek tabloları yedekten arındırılır, kalıcı veriler korunur."""
    _assert_shutil_never_called(monkeypatch)

    # Kalıcı tablolar
    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS scripts (id TEXT PRIMARY KEY, title TEXT, full_text TEXT)"
    )
    await db.execute_write(
        "INSERT INTO scripts (id, title, full_text) VALUES (?, ?, ?)",
        ("scr_001", "Kalıcı Senaryo", "Bu içerik yedeğe dahil edilmelidir."),
    )

    # Önbellek tabloları (cache_*, %_cache, temp_*)
    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS cache_transcripts (video_id TEXT PRIMARY KEY, transcript TEXT)"
    )
    await db.execute_write(
        "INSERT INTO cache_transcripts (video_id, transcript) VALUES (?, ?)",
        ("vid_temp_1", "Geçici transkript metni"),
    )
    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS youtube_cache (query TEXT PRIMARY KEY, result_json TEXT)"
    )
    await db.execute_write(
        "INSERT INTO youtube_cache (query, result_json) VALUES (?, ?)",
        ("yapay zeka", '{"items": []}'),
    )
    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS temp_search_results (id INT PRIMARY KEY, title TEXT)"
    )
    await db.execute_write(
        "INSERT INTO temp_search_results (id, title) VALUES (?, ?)",
        (1, "Geçici Arama"),
    )

    backup_file = tmp_path / "isolated_cache_backup.sqlite3"
    await async_create_backup(db, backup_file)

    assert backup_file.exists()
    conn = sqlite3.connect(str(backup_file))
    try:
        cur = conn.cursor()
        # Kalıcı tablo sağlam durmalı
        cur.execute("SELECT title, full_text FROM scripts WHERE id = ?", ("scr_001",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Kalıcı Senaryo"

        # Önbellek tabloları şemada var olmalı ancak içindeki satır sayısı COUNT(*) == 0 olmalı
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cache_transcripts', 'youtube_cache', 'temp_search_results')"
        )
        found_cache_tables = [r[0] for r in cur.fetchall()]
        assert set(found_cache_tables) == {"cache_transcripts", "youtube_cache", "temp_search_results"}

        for tbl in found_cache_tables:
            cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_corrupted_backup_rejected_with_corrupted_backup_error(
    db: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bozuk veya manipüle edilmiş byte'lı SQLite dosyası CorruptedBackupError ile reddedilir; canlı DB korunur."""
    _assert_shutil_never_called(monkeypatch)

    # Canlı veritabanına döngüyle 200 satır veri ekle
    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS live_critical_data (id INT PRIMARY KEY, token TEXT, payload TEXT)"
    )
    for i in range(200):
        await db.execute_write(
            "INSERT INTO live_critical_data (id, token, payload) VALUES (?, ?, ?)",
            (i, f"TOKEN_{i}", "x" * 256),
        )

    # Geçerli bir yedek al
    backup_file = tmp_path / "corrupted_candidate.sqlite3"
    await async_create_backup(db, backup_file)
    assert backup_file.exists()
    assert backup_file.stat().st_size > 4096  # Gerçek B-Tree için çoklu sayfa doğrulaması

    # 2. sayfayı (f.seek(4096)) bozarak gerçek B-Tree bozulmasını test et
    with open(backup_file, "r+b") as f:
        f.seek(4096)
        f.write(b"\xaa\xbb\xcc\xdd" * 64)

    # Geri yüklemeyi dene — CorruptedBackupError fırlatılmalı
    with pytest.raises(CorruptedBackupError) as exc_info:
        await async_restore_backup(backup_file, db)

    assert "bozuk" in str(exc_info.value).lower() or "bütünlük" in str(exc_info.value).lower()

    # Canlı veritabanının zarar görmediğini doğrula (200 satırın tamamı korunmalı)
    reader = await db.get_reader()
    try:
        async with reader.execute("SELECT COUNT(*) FROM live_critical_data") as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == 200
    finally:
        await reader.close()


@pytest.mark.asyncio
async def test_crash_recovery_resets_interrupted_jobs_to_checkpoint(
    db: Database,
) -> None:
    """Çökme sonrası asılı kalan RUNNING/RENDERING oturumlar kararlı checkpoint adımına kurtarılır."""
    repo = ProjectSessionRepository(db)
    await repo.init_table()

    # 1. RUNNING durumunda asılı kalan oturum
    await repo.save_session(
        session_id="session_running_crash",
        topic="Kuantum Fiziği",
        current_step="RENDER",
        checkpoint_step="PREVIEW",
        status="RUNNING",
        preview={"isVerified": True},
        audio={"voiceId": "v1"},
    )

    # 2. RENDERING durumunda asılı kalan oturum
    await repo.save_session(
        session_id="session_rendering_crash",
        topic="Yapay Zeka Tarihi",
        current_step="RENDER",
        checkpoint_step="SCRIPT",
        status="RENDERING",
        script={"id": "scr_99", "title": "YZ Tarihi"},
    )

    # 3. Başarıyla tamamlanmış oturum
    await repo.save_session(
        session_id="session_completed_ok",
        topic="Finans 101",
        current_step="RENDER",
        checkpoint_step="RENDER",
        status="COMPLETED",
        render={"progress": 100, "status": "COMPLETED"},
    )

    # Çökme kurtarma fonksiyonunu çalıştır
    recovered_count = await repo.recover_interrupted_sessions()
    assert recovered_count == 2

    # S1 kurtarma kontrolü: status RECOVERED, current_step PREVIEW
    recovered_s1 = await repo.get_session("session_running_crash")
    assert recovered_s1 is not None
    assert recovered_s1.status == "RECOVERED"
    assert recovered_s1.current_step == "PREVIEW"
    assert recovered_s1.checkpoint_step == "PREVIEW"
    assert recovered_s1.preview == {"isVerified": True}

    # S2 kurtarma kontrolü: status RECOVERED, current_step SCRIPT
    recovered_s2 = await repo.get_session("session_rendering_crash")
    assert recovered_s2 is not None
    assert recovered_s2.status == "RECOVERED"
    assert recovered_s2.current_step == "SCRIPT"
    assert recovered_s2.checkpoint_step == "SCRIPT"

    # S3 dokunulmamış olmalı
    normal_s3 = await repo.get_session("session_completed_ok")
    assert normal_s3 is not None
    assert normal_s3.status == "COMPLETED"
    assert normal_s3.current_step == "RENDER"

    # get_active_session çağrısı en güncel kurtarılan oturumu getirmeli
    active = await repo.get_active_session()
    assert active is not None
    assert active.status == "RECOVERED"


@pytest.mark.asyncio
async def test_valid_backup_restores_over_live_database_cleanly(
    db: Database,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canlı DB'ye veri yazılır, yedek alınır, veri silinir ve yedeğin geri yüklenmesiyle verinin eksiksiz döndüğü kanıtlanır."""
    _assert_shutil_never_called(monkeypatch)

    await db.execute_write(
        "CREATE TABLE IF NOT EXISTS critical_records (id INT PRIMARY KEY, name TEXT, content TEXT)"
    )

    # 1. Canlı DB'ye veri yaz
    await db.execute_write(
        "INSERT INTO critical_records (id, name, content) VALUES (?, ?, ?)",
        (101, "Proje Alpha", "Geri yüklenecek kritik içerik"),
    )
    await db.execute_write(
        "INSERT INTO critical_records (id, name, content) VALUES (?, ?, ?)",
        (102, "Proje Beta", "İkinci kritik kayıt"),
    )

    # Verinin yazıldığını doğrula
    reader = await db.get_reader()
    try:
        async with reader.execute("SELECT COUNT(*) FROM critical_records") as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == 2
    finally:
        await reader.close()

    # 2. Canlı veritabanından SQLite native yedeği al
    backup_file = tmp_path / "clean_restore_backup.sqlite3"
    await async_create_backup(db, backup_file)
    assert backup_file.exists()
    assert verify_backup(backup_file) is True

    # 3. Canlı DB'deki verileri sil (DELETE)
    await db.execute_write("DELETE FROM critical_records")

    # Verilerin silindiğini doğrula (COUNT == 0)
    reader = await db.get_reader()
    try:
        async with reader.execute("SELECT COUNT(*) FROM critical_records") as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row[0] == 0
    finally:
        await reader.close()

    # 4. Yedeği canlı veritabanına geri yükle
    await async_restore_backup(backup_file, db)

    # 5. Silinen verilerin eksiksiz ve bozulmadan geri geldiğini kanıtla
    reader = await db.get_reader()
    try:
        async with reader.execute(
            "SELECT id, name, content FROM critical_records ORDER BY id ASC"
        ) as cur:
            rows = list(await cur.fetchall())
            assert len(rows) == 2
            assert rows[0][0] == 101
            assert rows[0][1] == "Proje Alpha"
            assert rows[0][2] == "Geri yüklenecek kritik içerik"
            assert rows[1][0] == 102
            assert rows[1][1] == "Proje Beta"
            assert rows[1][2] == "İkinci kritik kayıt"
    finally:
        await reader.close()


@pytest.mark.asyncio
async def test_reader_pool_reuses_connections_and_enforces_foreign_keys(
    db: Database,
) -> None:
    """ReaderPool aynı aiosqlite bağlantısını yeniden kullanır (Zero-Thread-Churn) ve PRAGMA foreign_keys=ON zorlar."""
    import aiosqlite

    r1 = await db.get_reader()
    raw_conn_1 = r1._conn
    async with r1.execute("PRAGMA foreign_keys;") as cur:
        fk_row = await cur.fetchone()
        assert fk_row is not None and fk_row[0] == 1
    await r1.close()

    r2 = await db.get_reader()
    raw_conn_2 = r2._conn
    await r2.close()

    # Aynı bağlantı havuzdan geri dönmeli
    assert raw_conn_1 is raw_conn_2

    # Writer üzerinde de PRAGMA foreign_keys=ON zorlanmalı
    await db.execute_write("CREATE TABLE parent_tbl (id TEXT PRIMARY KEY)")
    await db.execute_write(
        "CREATE TABLE child_tbl (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES parent_tbl(id) ON DELETE CASCADE)"
    )
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute_write(
            "INSERT INTO child_tbl (id, parent_id) VALUES (?, ?)",
            ("c1", "non_existent_parent"),
        )


@pytest.mark.asyncio
async def test_executemany_write_commits_batch_in_single_transaction(
    db: Database,
) -> None:
    """executemany_write çoklu satırları tek bir atomik transaction içinde yazar."""
    await db.execute_write("CREATE TABLE batch_items (id INT PRIMARY KEY, label TEXT)")
    batch = [(i, f"item_{i}") for i in range(50)]
    await db.executemany_write("INSERT INTO batch_items (id, label) VALUES (?, ?)", batch)

    async with await db.get_reader() as reader:
        async with reader.execute("SELECT COUNT(*) FROM batch_items") as cur:
            row = await cur.fetchone()
            assert row is not None and row[0] == 50


@pytest.mark.asyncio
async def test_session_state_payload_envelope_roundtrip_preserves_all_fields(
    db: Database,
) -> None:
    """Frontend persistSessionToBackend tarafından gönderilen state_payload zarfı veri kaybı olmadan kaydedilir ve okunur."""
    from types import SimpleNamespace
    from services.core.hustler.api.routes.pipeline import (
        SaveSessionRequest,
        get_active_session,
        save_session,
    )

    repo = ProjectSessionRepository(db)
    await repo.init_table()
    fake_req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db, session_repo=repo)))

    payload = SaveSessionRequest(
        id="session_scr_123",
        topic="Kuantum Hesaplama",
        current_step="PREVIEW",
        checkpoint_step="PREVIEW",
        status="IDLE",
        state_payload={
            "topic": "Kuantum Hesaplama",
            "ideas": [{"id": "idea_1", "title": "Kuantum Çipleri", "score": 94.2}],
            "selectedIdea": {"id": "idea_1", "title": "Kuantum Çipleri", "score": 94.2},
            "script": {"id": "scr_123", "title": "Kuantum Çipleri", "isApproved": True},
            "audio": {"voiceId": "tr-TR-Standard-A", "audioPath": "cache/audio.wav", "isGenerated": True},
            "assets": {"allSlotsFilled": True, "slots": [{"slotId": "s1", "assignedPath": "assets/video/hook.mp4"}]},
            "preview": {"previewUrl": "assets/previews/scr_123_preview.mp4", "isVerified": True},
            "render": {"jobId": "job_1", "profile": "DRAFT", "status": "IDLE", "progress": 0},
        },
    )

    await save_session(payload, fake_req)  # type: ignore[arg-type]
    active_resp = await get_active_session(fake_req)  # type: ignore[arg-type]
    session_dict = active_resp["session"]
    assert isinstance(session_dict, dict)
    assert session_dict["id"] == "session_scr_123"
    assert session_dict["selected_idea"] == {"id": "idea_1", "title": "Kuantum Çipleri", "score": 94.2}
    sp = session_dict["state_payload"]
    assert isinstance(sp, dict)
    assert sp["selectedIdea"] == {"id": "idea_1", "title": "Kuantum Çipleri", "score": 94.2}
    assert sp["script"] == {"id": "scr_123", "title": "Kuantum Çipleri", "isApproved": True}
    assert sp["audio"] == {"voiceId": "tr-TR-Standard-A", "audioPath": "cache/audio.wav", "isGenerated": True}
    assert sp["preview"] == {"previewUrl": "assets/previews/scr_123_preview.mp4", "isVerified": True}


@pytest.mark.asyncio
async def test_bounded_reader_pool_never_exceeds_pool_size_and_rejects_after_close(
    tmp_path: Path,
) -> None:
    """12 eşzamanlı okuyucu aynı anda çalıştığında fiziksel bağlantı sayısı asla reader_pool_size (4) sınırını aşmaz ve close() sonrası RuntimeError fırlatır."""
    import asyncio

    bounded_db = Database(tmp_path / "bounded.db", reader_pool_size=4)
    await bounded_db.init()
    await bounded_db.execute_write("CREATE TABLE t (x INT)")
    await bounded_db.execute_write("INSERT INTO t (x) VALUES (1)")

    max_observed_conns = 0

    async def reader_worker() -> int:
        nonlocal max_observed_conns
        async with await bounded_db.get_reader() as r:
            max_observed_conns = max(max_observed_conns, len(bounded_db._all_reader_conns))
            await asyncio.sleep(0.01)
            async with r.execute("SELECT x FROM t") as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 0

    results = await asyncio.gather(*(reader_worker() for _ in range(12)))
    assert results == [1] * 12
    assert max_observed_conns <= 4
    assert len(bounded_db._all_reader_conns) <= 4

    await bounded_db.close()
    assert len(bounded_db._all_reader_conns) == 0

    with pytest.raises(RuntimeError, match="Database is closed"):
        await bounded_db.get_reader()

    with pytest.raises(RuntimeError, match="Database is closed"):
        await bounded_db.execute_write("INSERT INTO t (x) VALUES (2)")


