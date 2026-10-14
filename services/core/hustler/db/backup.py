"""
K-802: SQLite Yerel Backup API ve Önbellek İzolasyonu Motoru
- shutil.copy KESİNLİKLE YASAKTIR; SQLite native connection.backup() API'si kullanılır.
- Yedekleme sırasında önbellek tabloları (cache_*, youtube_cache, *_cache) hariç tutulur ve VACUUM çalıştırılır.
- Geri yükleme (restore_backup) öncesinde PRAGMA integrity_check ve şema doğrulaması yapılır.
- Bozuk veya tahrif edilmiş yedekler CorruptedBackupError ile canlı veritabanına dokunulmadan reddedilir.
"""

import asyncio
from pathlib import Path
import sqlite3
from typing import Callable, Optional, Sequence
import structlog

logger = structlog.get_logger()


class BackupError(Exception):
    """Veritabanı yedekleme veya geri yükleme hatası."""


class CorruptedBackupError(BackupError):
    """Bozuk, geçersiz veya bütünlük testinden geçemeyen yedek dosyası hatası."""


EXCLUDED_TABLE_PATTERNS: Sequence[str] = (
    "cache_%",
    "%_cache",
    "youtube_cache",
    "temp_%",
)


def is_cache_table(table_name: str) -> bool:
    name = table_name.lower()
    if name == "youtube_cache":
        return True
    if name.startswith("cache_") or name.endswith("_cache") or name.startswith("temp_"):
        return True
    return False


def verify_backup(backup_path: Path | str) -> bool:
    """
    Yedek dosyasının bütünlüğünü ve geçerli bir SQLite veritabanı olduğunu denetler.
    Bozuk veya manipüle edilmiş dosyalarda CorruptedBackupError fırlatır.
    """
    path = Path(backup_path)
    if not path.exists():
        raise CorruptedBackupError(f"Yedek dosyası bulunamadı: {path}")

    if path.stat().st_size == 0:
        raise CorruptedBackupError(f"Yedek dosyası boş (0 byte): {path}")

    try:
        # URI bağlantısı ve salt-okunur mod
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            # 1. Bütünlük Kontrolü (PRAGMA integrity_check)
            cursor = conn.execute("PRAGMA integrity_check;")
            rows = cursor.fetchall()
            if not rows or rows[0][0] != "ok":
                err_msg = "; ".join(str(r[0]) for r in rows) if rows else "Bilinmeyen bütünlük hatası"
                raise CorruptedBackupError(f"Yedek bütünlük doğrulaması (integrity_check) başarısız: {err_msg}")

            # 2. Tablo ve Şema Varlığı Denetimi
            cursor = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            table_count = cursor.fetchone()[0]
            if table_count == 0:
                raise CorruptedBackupError("Yedek dosyasında hiçbir tablo veya şema tanımı bulunamadı")

        finally:
            conn.close()

    except sqlite3.DatabaseError as e:
        logger.error("backup_verification_failed", error=str(e), path=str(path))
        raise CorruptedBackupError(f"SQLite veritabanı okunamadı veya dosya bozuk: {e}") from e
    except Exception as e:
        if isinstance(e, CorruptedBackupError):
            raise
        raise CorruptedBackupError(f"Yedek doğrulama sırasında beklenmeyen hata: {e}") from e

    return True


def _resolve_path(target: Path | str | object) -> Path:
    if hasattr(target, "db_path"):
        return Path(getattr(target, "db_path"))
    if hasattr(target, "path"):
        p = getattr(target, "path")
        return Path(p) if not callable(p) else Path(p())
    if isinstance(target, Path):
        return target
    return Path(str(target))


def create_backup(
    source_db_path: Path | str | object,
    target_backup_path: Path | str | object,
    pages_per_step: int = 250,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> Path:
    """
    SQLite'ın yerel backup() API'sini kullanarak canlı WAL veritabanının yedeğini alır.
    shutil.copy ASLA kullanılmaz.
    Yedek hedefindeki tüm önbellek tablolarını (cache_*, youtube_cache vb.) DELETE FROM
    ile temizler ve diske yazılacak alanı VACUUM ile küçültür.
    """
    src_path = _resolve_path(source_db_path)
    dst_path = _resolve_path(target_backup_path)

    if not src_path.exists():
        raise BackupError(f"Kaynak veritabanı dosyası bulunamadı: {src_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Hedef dosya önceden varsa sıfırdan oluşturmak için kaldır
    if dst_path.exists():
        dst_path.unlink()

    src_conn: Optional[sqlite3.Connection] = None
    dst_conn: Optional[sqlite3.Connection] = None

    try:
        # Canlı WAL veritabanına eşzamanlı yazma sürerken bağlanılabilir
        src_conn = sqlite3.connect(str(src_path), timeout=30.0)
        dst_conn = sqlite3.connect(str(dst_path), timeout=30.0)

        # SQLite C-seviyesi yerel Online Backup API çağrısı
        src_conn.backup(dst_conn, pages=pages_per_step, progress=progress_callback)

        # Önbellek tablolarının tespiti ve yedekten temizlenmesi (DELETE FROM)
        cursor = dst_conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        cleaned_tables: list[str] = []
        for tbl in tables:
            if is_cache_table(tbl):
                dst_conn.execute(f"DELETE FROM [{tbl}];")
                cleaned_tables.append(tbl)

        dst_conn.commit()

        # Önbellek kaldırıldıktan sonra ayrılmış sayfaları işletim sistemine iade et
        dst_conn.execute("VACUUM;")
        dst_conn.commit()

        logger.info(
            "sqlite_backup_completed",
            source=str(src_path),
            target=str(dst_path),
            excluded_tables=cleaned_tables,
            backup_size_bytes=dst_path.stat().st_size,
        )

    except Exception as e:
        logger.error("sqlite_backup_failed", error=str(e), source=str(src_path))
        if dst_path.exists():
            try:
                dst_path.unlink()
            except OSError:
                pass
        raise BackupError(f"Yedekleme işlemi başarısız oldu: {e}") from e
    finally:
        if dst_conn:
            dst_conn.close()
        if src_conn:
            src_conn.close()

    # Üretilen yedeğin bütünlüğünü doğrula
    verify_backup(dst_path)
    return dst_path


def restore_backup(
    backup_path: Path | str | object,
    target_db_path: Path | str | object,
    pages_per_step: int = 250,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> None:
    """
    Yedek dosyasını canlı/hedef veritabanına SQLite yerel backup() API'si ile geri yükler.
    shutil.copy KESİNLİKLE kullanılmaz.
    Geri yükleme öncesinde PRAGMA integrity_check çalıştırılır; bozuk yedeklerde
    canlı veritabanına KESİNLİKLE DOKUNULMAZ.
    """
    b_path = _resolve_path(backup_path)
    t_path = _resolve_path(target_db_path)

    # 1. Aşama: Yedek dosyasını acımasızca doğrula (Canlı hedefe dokunmadan önce!)
    verify_backup(b_path)

    t_path.parent.mkdir(parents=True, exist_ok=True)

    backup_conn: Optional[sqlite3.Connection] = None
    target_conn: Optional[sqlite3.Connection] = None

    try:
        backup_conn = sqlite3.connect(str(b_path), timeout=30.0)
        target_conn = sqlite3.connect(str(t_path), timeout=30.0)

        # Yerel SQLite API ile yedeği hedefe aktar
        backup_conn.backup(target_conn, pages=pages_per_step, progress=progress_callback)

        # Hedef veritabanında WAL ve senkron ayarlarını yapılandır
        target_conn.execute("PRAGMA journal_mode=WAL;")
        target_conn.execute("PRAGMA synchronous=NORMAL;")
        target_conn.commit()

        logger.info(
            "sqlite_restore_completed",
            backup=str(b_path),
            target=str(t_path),
        )

    except Exception as e:
        logger.error("sqlite_restore_failed", error=str(e), backup=str(b_path))
        raise BackupError(f"Geri yükleme işlemi başarısız oldu: {e}") from e
    finally:
        if target_conn:
            target_conn.close()
        if backup_conn:
            backup_conn.close()


async def async_create_backup(
    source_db_path: Path | str | object,
    target_backup_path: Path | str | object,
    pages_per_step: int = 250,
) -> Path:
    """Asenkron bağlamlar için event loop bloklamayan yedekleme sarmalayıcısı."""
    return await asyncio.to_thread(create_backup, source_db_path, target_backup_path, pages_per_step)


async def async_restore_backup(
    backup_path: Path | str | object,
    target_db_path: Path | str | object,
    pages_per_step: int = 250,
) -> None:
    """Asenkron bağlamlar için event loop bloklamayan geri yükleme sarmalayıcısı."""
    await asyncio.to_thread(restore_backup, backup_path, target_db_path, pages_per_step)
