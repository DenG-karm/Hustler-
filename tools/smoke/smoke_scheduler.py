from services.core.hustler.services.discovery import DiscoveryOrchestrator
from typing import Any
import asyncio
import os
import sys
from pathlib import Path
import structlog

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.db import Database
from services.core.hustler.tasks.scheduler import discovery_loop, maintenance_loop

logger = structlog.get_logger()

# Mock Orchestrator: Hata simülasyonu için
class MockOrchestrator(DiscoveryOrchestrator):
    def __init__(self) -> None:
        self.call_count = 0
        
    async def run_discovery(self, topic: str, max_results: int = 50, score_threshold: float = 30.0) -> dict[str, Any]:
        self.call_count += 1
        logger.info("MockOrchestrator.run_discovery cagirildi", call_count=self.call_count)
        
        # İlk turda kasıtlı patlatıyoruz
        if self.call_count == 1:
            logger.warning("KASITLI HATA FIRLATILIYOR (1. Çağrı)")
            raise RuntimeError("YouTube API 500 Internal Server Error (Kasıtlı Çökme)")
        else:
            logger.info("MockOrchestrator.run_discovery başarılı (2. Çağrı)")
            return {"status": "success"}


async def main() -> None:
    logger.info("--- K-206 ZAMANLAYICI VE HATA İZOLASYON TESTİ BAŞLIYOR ---")
    
    db_path = Path("test_scheduler.db")
    db = Database(db_path)
    await db.init()
    
    # Tabloyu kuralım ki DELETE çalışırken patlamasın
    await db.execute_write("""
        CREATE TABLE IF NOT EXISTS youtube_cache (
            cache_key TEXT PRIMARY KEY,
            response_json TEXT,
            created_at REAL
        )
    """)

    mock_orchestrator = MockOrchestrator()
    
    # 1. FastAPI Lifespan Bağlamı Simülasyonu
    logger.info("Arka plan zamanlayıcıları 2'şer saniye periyotla başlatılıyor...")
    discovery_task = asyncio.create_task(
        discovery_loop(mock_orchestrator, "test topic", interval_sec=2)
    )
    maintenance_task = asyncio.create_task(
        maintenance_loop(db, cache_ttl_sec=3600, interval_sec=2)
    )
    
    # 2. Ana Thread / Event Loop Simülasyonu
    # 5.5 saniye bekleyip görevleri izleyeceğiz
    # 2. sn -> 1. çağrı (Çökecek ve yutulacak)
    # 4. sn -> 2. çağrı (Başarılı olacak, döngünün kırılmadığı kanıtlanacak)
    logger.info("Ana event loop uyutuluyor (5.5 saniye)")
    await asyncio.sleep(5.5)
    
    logger.info("Test süresi doldu, görevler iptal ediliyor (Tear down)")
    discovery_task.cancel()
    maintenance_task.cancel()
    
    try:
        await asyncio.gather(discovery_task, maintenance_task)
    except asyncio.CancelledError:
        pass
        
    await db.close()
    
    # Temizlik
    if db_path.exists(): db_path.unlink()
    try:
        if db_path.with_suffix(".db-shm").exists(): db_path.with_suffix(".db-shm").unlink()
        if db_path.with_suffix(".db-wal").exists(): db_path.with_suffix(".db-wal").unlink()
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())
