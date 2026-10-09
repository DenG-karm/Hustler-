import asyncio
import os
import sys
from pathlib import Path
import structlog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.db import Database
from services.core.hustler.storage.cache import YouTubeCache
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.services.discovery import DiscoveryOrchestrator

logger = structlog.get_logger()

async def main() -> None:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY eksik!")
        return

    db_path = Path("test_discovery.db")
    db = Database(db_path)
    await db.init()

    cache = YouTubeCache(db, ttl_seconds=3600)
    await cache.init_tables()

    topic = "day trading smc"

    async with YouTubeClient(api_key=api_key, cache=cache) as client:
        orchestrator = DiscoveryOrchestrator(client, db)
        await orchestrator.init_tables()
        
        logger.info("--- Discovery Servisi Çalıştırılıyor ---", topic=topic)
        
        # Test amaçlı Threshold: 10.0 ayarlayalım ki bir kaç sonuç kesin geçebilsin (niş konu için)
        results = await orchestrator.run_discovery(topic, max_results=30, score_threshold=10.0)
        
        logger.info("=== DISCOVERY TEST SONUÇLARI ===")
        logger.info("Toplam Çekilen Video", sayi=results["fetched"])
        logger.info("Eşiğe Takılıp Elenen Video (Çöpe Giden)", sayi=results["discarded"])
        logger.info("Veritabanına Yazılan Kazananlar", sayi=results["inserted"])
        logger.info("En Yüksek Skor", max_score=round(results["max_score"], 2))
        
        # Test doğrulamaları
        assert results["fetched"] > 0, "Video bulunamadı!"
        assert results["discarded"] + results["inserted"] == results["fetched"]
        
    await db.close()
    
    # Test DB Temizliği
    if db_path.exists(): db_path.unlink()
    try:
        if db_path.with_suffix(".db-shm").exists(): db_path.with_suffix(".db-shm").unlink()
        if db_path.with_suffix(".db-wal").exists(): db_path.with_suffix(".db-wal").unlink()
    except Exception:
        pass
        
if __name__ == "__main__":
    asyncio.run(main())
