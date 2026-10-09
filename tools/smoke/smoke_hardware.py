import asyncio
import os
import sys
import structlog
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.hardware import init_hardware_profile, measure_and_save_profile

logger = structlog.get_logger()

async def main() -> None:
    logger.info("--- M3 K-301: HARDWARE PROFILE TESTİ BAŞLIYOR ---")
    
    db_path = Path("hustler_core.db")
    db = Database(db_path)
    await db.init()
    
    logger.info("Donanım taraması başlatılıyor (Lazy CUDA & RTF Benchmark)...")
    await init_hardware_profile(db)
    
    profile = await measure_and_save_profile(db)
    
    logger.info("=== TESPİT EDİLEN DONANIM PROFİLİ ===",
        cuda_bulundu_mu=profile["has_cuda"],
        rtf_skoru=profile["rtf_score"]
    )
    
    # WriterQueue üzerinden yazıldığını doğrulamak için geri okuma yapalım
    logger.info("Veritabanından teyit ediliyor...")
    conn = await db.get_reader()
    async with conn.execute("SELECT has_cuda, rtf_score, updated_at FROM hardware_profile WHERE id=1") as cursor:
        row = await cursor.fetchone()
        
    await conn.close()
    await db.close()
    
    assert row is not None, "Veritabanına profil kaydedilemedi!"
    
    logger.info("=== VERİTABANI KAYDI BAŞARILI ===",
        db_has_cuda=bool(row[0]),
        db_rtf_score=row[1],
        timestamp=row[2]
    )
    
if __name__ == "__main__":
    asyncio.run(main())
