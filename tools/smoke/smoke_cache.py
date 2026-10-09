import asyncio
import os
import time
import sys
from pathlib import Path
import structlog

# Proje kök dizinini Python PATH'ine ekle (tools/ icinden calistirinca services'i bulabilmesi icin)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.db import Database
from services.core.hustler.storage.cache import YouTubeCache
from services.core.hustler.adapters.youtube import YouTubeClient

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()

async def main() -> None:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY eksik! Lütfen $env:YOUTUBE_API_KEY ayarlayın.")
        return

    # Veritabanı dosyası ayarla
    db_path = Path("test_cache_layer.db")
    db = Database(db_path)
    await db.init()

    # Önbellek (Cache) Katmanını ayağa kaldır (3600 sn TTL)
    cache = YouTubeCache(db, ttl_seconds=3600)
    await cache.init_tables()

    topic = "python caching system"

    async with YouTubeClient(api_key=api_key, cache=cache) as client:
        # İLK İSTEK (API'YE GİDECEK)
        logger.info("=============================================")
        logger.info("İLK ARAMA BAŞLIYOR (API'ye gitmeli, Kota Harcamalı)")
        logger.info("=============================================")
        start = time.perf_counter()
        
        # AsyncGenerator üzerinden pagination (sayfalama) testi
        results_1 = [item async for item in client.search_shorts(topic, max_results=10)]
        
        elapsed_1 = (time.perf_counter() - start) * 1000
        quota_1 = client.quota_used
        
        logger.info(
            "1. İstek Tamamlandı", 
            gecen_sure_ms=round(elapsed_1, 2), 
            toplam_kota_harcamasi=quota_1,
            sonuc_sayisi=len(results_1)
        )
        
        # İKİNCİ İSTEK (CACHE'DEN DÖNECEK)
        logger.info("=============================================")
        logger.info("İKİNCİ ARAMA BAŞLIYOR (Doğrudan DB/Cache'den dönmeli, Sıfır Kota)")
        logger.info("=============================================")
        
        client.quota_used = 0 # Önceki harcamayı sıfırlayalım ki cache hit netleşsin
        start = time.perf_counter()
        
        # Aynı çağrı tekrar
        results_2 = [item async for item in client.search_shorts(topic, max_results=10)]
        
        elapsed_2 = (time.perf_counter() - start) * 1000
        quota_2 = client.quota_used
        
        logger.info(
            "2. İstek Tamamlandı", 
            gecen_sure_ms=round(elapsed_2, 2), 
            toplam_kota_harcamasi=quota_2,
            sonuc_sayisi=len(results_2)
        )

        assert elapsed_2 < 50, f"Cache hızı beklenen sürenin üstünde! {elapsed_2}ms"
        assert quota_2 == 0, "İkinci istek kota harcadı!"
        
    await db.close()
    
    # Test sonrası db temizliği
    if db_path.exists():
        db_path.unlink()
    try:
        shm_path = db_path.with_suffix(".db-shm")
        wal_path = db_path.with_suffix(".db-wal")
        if shm_path.exists(): shm_path.unlink()
        if wal_path.exists(): wal_path.unlink()
    except Exception:
        pass
        
if __name__ == "__main__":
    asyncio.run(main())
