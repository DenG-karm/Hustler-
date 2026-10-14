"""
K-803: Tanılama Zip Paketi Üreticisi (Diagnostic Bundler).
- Geçici veya hedef dizinde hustler_diag_<timestamp>.zip üretir.
- doctor.json, versions.json, logs/recent.log ve session_summary.json dosyalarını paketler.
- Medya dosyaları (.mp4, .mp3, .wav) ve ham SQLite veritabanı KESİNLİKLE pakete dahil edilmez.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sqlite3
from typing import Optional, Sequence
import structlog

from services.core.hustler.db.engine import Database
from services.core.hustler.diagnostics.doctor import run_system_doctor
from services.core.hustler.diagnostics.redactor import redact_sensitive_text

logger = structlog.get_logger()

# Pakete dahil edilmesi mimari olarak kesinlikle yasak olan uzantılar
FORBIDDEN_EXTENSIONS: Sequence[str] = (
    ".mp4",
    ".mp3",
    ".wav",
    ".webm",
    ".sqlite3",
    ".db",
    ".db-wal",
    ".db-shm",
)

MAX_LOG_BYTES: int = 2 * 1024 * 1024  # Maksimum 2 MB log
MAX_LOG_LINES: int = 1000  # Maksimum 1000 satır tail


def _get_versions_info(db: Database) -> dict[str, object]:
    """Uygulama, Python, SQLite ve şema sürüm bilgilerini derler."""
    schema_version: int = 0
    tables: list[str] = []

    if db.path.exists():
        try:
            conn = sqlite3.connect(f"file:{db.path.resolve()}?mode=ro", uri=True, timeout=5.0)
            try:
                cur = conn.execute("PRAGMA user_version;")
                row = cur.fetchone()
                schema_version = int(row[0]) if row else 0

                cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [str(r[0]) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception:
            pass

    return {
        "app_version": "0.1.0",
        "python_version": platform.python_version(),
        "sqlite_version": sqlite3.sqlite_version,
        "schema_version": schema_version,
        "database_tables": tables,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "packages": {
            "core": "0.1.0",
            "fastapi": ">=0.115.0",
            "pydantic": ">=2.0",
            "structlog": ">=24.0",
            "aiosqlite": ">=0.20.0",
        },
    }


def _read_recent_log(log_path: Optional[Path] = None) -> str:
    """En güncel log dosyasından son N satır/baytı okur ve maskeler."""
    candidates: list[Path] = []
    if log_path:
        candidates.append(log_path)
    candidates.extend([
        Path("logs/app.log"),
        Path("logs/hustler.log"),
        Path("logs/hustler_core.log"),
        Path("app.log"),
        Path("hustler.log"),
    ])

    target: Optional[Path] = None
    for c in candidates:
        if c.exists() and c.is_file():
            target = c
            break

    if not target:
        iso_now = datetime.now(timezone.utc).isoformat()
        return redact_sensitive_text(
            f"{iso_now} [INFO] Diagnostic bundle generated. No on-disk log file found.\n"
        )

    try:
        file_size = target.stat().st_size
        with open(target, "rb") as f:
            if file_size > MAX_LOG_BYTES:
                f.seek(file_size - MAX_LOG_BYTES)
                f.readline()  # Kısmi satırı atla
            raw_bytes = f.read()

        raw_text = raw_bytes.decode("utf-8", errors="replace")
        lines = raw_text.splitlines()[-MAX_LOG_LINES:]
        return redact_sensitive_text("\n".join(lines) + "\n")
    except Exception as e:
        iso_now = datetime.now(timezone.utc).isoformat()
        return redact_sensitive_text(
            f"{iso_now} [ERROR] Failed to read log file: {e}\n"
        )


def _get_session_summary(db: Database) -> dict[str, object]:
    """Aktif projenin durumunu metin içeriklerinden arındırılmış meta özet olarak döner."""
    if not db.path.exists():
        return {"active_session": None, "reason": "database_not_created"}

    try:
        conn = sqlite3.connect(f"file:{db.path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            cur = conn.execute(
                """
                SELECT session_id, topic, current_step, checkpoint_step, status,
                       script_json, audio_json, preview_json, render_json,
                       last_error, updated_at
                FROM project_sessions
                ORDER BY updated_at DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            if not row:
                return {"active_session": None, "reason": "no_sessions_found"}

            (
                session_id,
                topic,
                current_step,
                checkpoint_step,
                status,
                script_j,
                audio_j,
                preview_j,
                render_j,
                last_err,
                updated_at,
            ) = row

            # Senaryo metin içeriği hariç meta verisi
            script_meta: dict[str, object] = {}
            if script_j:
                try:
                    sd = json.loads(script_j)
                    if isinstance(sd, dict):
                        script_meta = {
                            "id": sd.get("id"),
                            "title": sd.get("title"),
                            "has_full_text": bool(sd.get("full_text")),
                        }
                except Exception:
                    script_meta = {"parse_error": True}

            # Ses URL ve ID meta verisi
            audio_meta: dict[str, object] = {}
            if audio_j:
                try:
                    ad = json.loads(audio_j)
                    if isinstance(ad, dict):
                        audio_meta = {
                            "voice_id": ad.get("voiceId"),
                            "has_audio": bool(ad.get("audioUrl")),
                        }
                except Exception:
                    audio_meta = {"parse_error": True}

            # Önizleme ve Render meta verisi
            preview_meta: dict[str, object] = {}
            if preview_j:
                try:
                    pd = json.loads(preview_j)
                    if isinstance(pd, dict):
                        preview_meta = {"is_verified": pd.get("isVerified")}
                except Exception:
                    preview_meta = {"parse_error": True}

            render_meta: dict[str, object] = {}
            if render_j:
                try:
                    rd = json.loads(render_j)
                    if isinstance(rd, dict):
                        render_meta = {
                            "status": rd.get("status"),
                            "progress": rd.get("progress"),
                        }
                except Exception:
                    render_meta = {"parse_error": True}

            return {
                "active_session": {
                    "session_id": str(session_id),
                    "topic": str(topic),
                    "current_step": str(current_step),
                    "checkpoint_step": str(checkpoint_step),
                    "status": str(status),
                    "script": script_meta,
                    "audio": audio_meta,
                    "preview": preview_meta,
                    "render": render_meta,
                    "last_error": last_err,
                    "updated_at": updated_at,
                }
            }
        finally:
            conn.close()
    except Exception as e:
        return {"active_session": None, "error": str(e)}


def create_diagnostics_bundle(
    output_dir: Path,
    db: Database,
    log_path: Optional[Path] = None,
) -> Path:
    """
    Geçici bellekte veya hedef dizinde hustler_diag_<timestamp>.zip üretir.
    Medya dosyaları ve ham SQLite veritabanı KESİNLİKLE pakete dahil edilmez.
    """
    import zipfile

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_filename = f"hustler_diag_{timestamp}.zip"
    target_zip = output_dir / zip_filename

    # 1. doctor.json
    report = run_system_doctor(db)
    doctor_json = redact_sensitive_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False)
    )

    # 2. versions.json
    versions_data = _get_versions_info(db)
    versions_json = redact_sensitive_text(
        json.dumps(versions_data, indent=2, ensure_ascii=False)
    )

    # 3. logs/recent.log
    recent_log_text = _read_recent_log(log_path)

    # 4. session_summary.json
    session_summary_data = _get_session_summary(db)
    session_summary_json = redact_sensitive_text(
        json.dumps(session_summary_data, indent=2, ensure_ascii=False)
    )

    files_to_pack: dict[str, str] = {
        "doctor.json": doctor_json,
        "versions.json": versions_json,
        "logs/recent.log": recent_log_text,
        "session_summary.json": session_summary_json,
    }

    # Kural ihlali denetimi
    for arcname in files_to_pack:
        for forbidden in FORBIDDEN_EXTENSIONS:
            if arcname.lower().endswith(forbidden):
                raise ValueError(
                    f"MİMARİ KURAL İHLALİ: {forbidden} uzantılı dosya tanılama paketine eklenemez!"
                )

    with zipfile.ZipFile(target_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in files_to_pack.items():
            zf.writestr(arcname, content)

    logger.info(
        "diagnostics_bundle_created",
        bundle_path=str(target_zip),
        size_bytes=target_zip.stat().st_size,
    )

    return target_zip


async def async_create_diagnostics_bundle(
    output_dir: Path,
    db: Database,
    log_path: Optional[Path] = None,
) -> Path:
    """Asenkron bağlamlar için iş parçacığı havuzu sarmalayıcısı."""
    return await asyncio.to_thread(create_diagnostics_bundle, output_dir, db, log_path)


def main() -> None:
    """CLI giriş noktası: python -m services.core.hustler.diagnostics.bundler"""
    parser = argparse.ArgumentParser(description="Hustler Diagnostic Bundle Generator")
    parser.add_argument("--output", "-o", default="runs/diagnostics", help="Hedef dizin")
    parser.add_argument("--db", "-d", default="hustler_core.db", help="Veritabanı yolu")
    args = parser.parse_args()

    db = Database(Path(args.db))
    bundle_path = create_diagnostics_bundle(Path(args.output), db)
    print(f"Tanılama paketi başarıyla üretildi: {bundle_path.resolve()}")


if __name__ == "__main__":
    main()
