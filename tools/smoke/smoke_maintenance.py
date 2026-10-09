import asyncio
import os
import sys
import time
from pathlib import Path
import structlog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.db import Database
from services.core.hustler.tasks.scheduler import maintenance_loop

logger = structlog.get_logger()

async def main() -> None:
    logger.info("--- K-203 VERİ KATMANI BAKIMI TESTİ BAŞLIYOR ---")
    
    db_path = Path("test_maintenance.db")
    db = Database(db_path)
    await db.init()
    
    # 1. Tablo Oluşturma
    await db.execute_write("""
        CREATE TABLE IF NOT EXISTS youtube_cache (
            cache_key TEXT PRIMARY KEY,
            response_json TEXT,
            created_at REAL
        )
    """)

    # 2. Manuel Olarak Geçmiş 10 Sahte Kayıt (Expired) Ekleme
    logger.info("Veritabanına 10 adet süresi dolmuş (expired) kayıt ekleniyor...")
    expired_time = time.time() - 5000  # 5000 saniye önce 
    
    for i in range(10):
        await db.execute_write(
            "INSERT INTO youtube_cache (cache_key, response_json, created_at) VALUES (?, ?, ?)",
            (f"old_key_{i}", '{"data": "dummy"}', expired_time)
        )
        
    # 3. Geçerli 1 Kayıt (Fresh) Ekleme (Silinmemeli)
    valid_time = time.time()
    await db.execute_write(
        "INSERT INTO youtube_cache (cache_key, response_json, created_at) VALUES (?, ?, ?)",
        ("valid_key", '{"data": "fresh"}', valid_time)
    )

    # İşlem Öncesi DB Kontrolü
    conn = await db.get_reader()
    async with conn.execute("SELECT COUNT(*) FROM youtube_cache") as cursor:
        row = await cursor.fetchone()
        initial_count = row[0] if row else 0
    await conn.close()
    
    logger.info(f"Başlangıç: Toplam {initial_count} kayıt var. (10 expired, 1 valid)")
    assert initial_count == 11, "Kayıtlar eksik eklendi!"

    # 4. Zamanlayıcıyı (Scheduler) 5 Saniyelik Periyotla Başlat
    maintenance_task = asyncio.create_task(
        maintenance_loop(db, cache_ttl_sec=3600, interval_sec=5)
    )
    
    # 5. Bekleme (Döngünün 1 Kere Tetiklenmesi İçin 6 Saniye)
    logger.info("Bakım döngüsünün tetiklenmesi için 6 saniye bekleniyor...")
    await asyncio.sleep(6)
    
    # 6. Temizlik Sonrası İşlem Sonucu Kontrolü
    conn = await db.get_reader()
    async with conn.execute("SELECT COUNT(*) FROM youtube_cache") as cursor:
        row = await cursor.fetchone()
        final_count = row[0] if row else 0
    await conn.close()
    
    logger.info(f"Temizlik Sonrası: Toplam {final_count} kayıt kaldı. (Beklenen: 1)")
    
    assert final_count == 1, f"Yanlış sayıda kayıt kaldı! Beklenen 1, kalan {final_count}"
    
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass
        
    await db.close()
    
    # DB Temizliği
    if db_path.exists(): db_path.unlink()
    try:
        if db_path.with_suffix(".db-shm").exists(): db_path.with_suffix(".db-shm").unlink()
        if db_path.with_suffix(".db-wal").exists(): db_path.with_suffix(".db-wal").unlink()
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())
