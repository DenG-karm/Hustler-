import asyncio
import time
import structlog

from services.core.hustler.db import Database
from services.core.hustler.services.discovery import DiscoveryOrchestrator
from services.core.hustler.storage.maintenance import prune_expired_cache

logger = structlog.get_logger()

async def discovery_loop(orchestrator: DiscoveryOrchestrator, topic: str, interval_sec: int):
    """
    Otonom Keşif Döngüsü
    Verilen aralıklarla arka planda video araması ve skorlaması yapar.
    Hata izolasyonu içerir, asla çökmez.
    """
    logger.info("Discovery Zamanlayıcısı Başladı", interval_sec=interval_sec, topic=topic)
    while True:
        try:
            # 1. Periyot Beklemesi
            await asyncio.sleep(interval_sec)
            
            # 2. İşlem
            logger.debug("Discovery döngüsü tetiklendi", topic=topic)
            # Default parametrelerle çağırıyoruz, skor vs ihtiyaca göre dışarıdan alınabilir
            await orchestrator.run_discovery(topic, max_results=20, score_threshold=30.0)
            
        except asyncio.CancelledError:
            logger.info("Discovery Zamanlayıcısı durduruldu (Cancelled)")
            break
        except Exception as e:
            # 3. Devre İzolasyonu (Circuit Safety)
            logger.error(
                "Discovery döngüsünde hata yakalandı, yutuldu", 
                error=str(e), 
                err_type=type(e).__name__
            )


async def maintenance_loop(db: Database, cache_ttl_sec: int, interval_sec: int):
    """
    Veritabanı Bakım ve Temizlik Döngüsü
    Süresi dolmuş önbelleği (Cache) siler ve incremental_vacuum ile boşalan RAM/Diski OS'e iade eder.
    Hata izolasyonu içerir.
    """
    logger.info("Bakım Zamanlayıcısı Başladı", interval_sec=interval_sec)
    while True:
        try:
            # 1. Periyot Beklemesi
            await asyncio.sleep(interval_sec)
            
            # 2. İşlem
            logger.debug("Bakım döngüsü tetiklendi")
            # K-203 modülü üzerinden temizlik (DELETE + VACUUM) yapılır
            await prune_expired_cache(db, ttl_seconds=cache_ttl_sec)
            
        except asyncio.CancelledError:
            logger.info("Bakım Zamanlayıcısı durduruldu (Cancelled)")
            break
        except Exception as e:
            # 3. Devre İzolasyonu (Circuit Safety)
            logger.error(
                "Bakım döngüsünde hata yakalandı, yutuldu", 
                error=str(e), 
                err_type=type(e).__name__
            )
