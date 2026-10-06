import time
import structlog
from services.core.hustler.db import Database

logger = structlog.get_logger()

async def prune_expired_cache(db: Database, ttl_seconds: int = 3600):
    """
    K-203: Önbellek (Cache) Temizleme ve Disk İade Etme (Vacuum) Rutini.
    Disk I/O darboğazını önlemek için işlemler asenkron WriterQueue üzerinden ilerler.
    """
    expire_threshold = time.time() - ttl_seconds
    
    # 1. Eski kayıtları sil (WriterQueue)
    await db.execute_write(
        "DELETE FROM youtube_cache WHERE created_at < ?", 
        (expire_threshold,)
    )
    
    # 2. Boşa çıkan disk bloklarını OS'e iade et (PRAGMA incremental_vacuum)
    await db.trigger_maintenance()
    
    logger.info("Veritabanı bakımı (Pruning & Vacuum) başarıyla tamamlandı", threshold_ts=expire_threshold)
