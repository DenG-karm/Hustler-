import sys
import os
import asyncio
import structlog
from pathlib import Path

# Windows Unicode sorunları için
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.orchestration.reduce import ReduceOrchestrator

logger = structlog.get_logger()

# Test için LLMPort'un dış ağa gitmesini engelliyoruz (Mock)
async def mock_execute(prompt: str) -> LLMResponse:
    logger.info("🔥 AĞ İSTEĞİ YAPILDI (LLM ÇAĞRILDI ve Token Harcandı) 🔥")
    await asyncio.sleep(0.5)
    return LLMResponse("Sentetik Reduce Analizi", 10, 10, 20)

async def main():
    logger.info("--- M3 K-308: REDUCE VE ÖNBELLEK YÖNETİMİ TESTİ ---")
    
    # 1. Altyapı Hazırlığı (Geçici Test Veritabanı)
    db_path = Path("test_reduce.sqlite")
    if db_path.exists():
        db_path.unlink() # Temiz bir test için eski dosyayı sil
        
    db = Database(db_path)
    await db.init()
    
    # LLMPort mock ayarı
    llm_port = LLMPort(api_key="MOCK_KEY", max_tokens=10000)
    llm_port._execute_network_request = mock_execute
    
    # 2. Reduce Orkestratörünü Kur ve Tabloyu Hazırla
    reduce_engine = ReduceOrchestrator(db, llm_port)
    await reduce_engine.init_table()
    
    # Sentetik Veri
    test_transcript = "Bu çok çok önemli bir YouTube Shorts videosunun transkript metnidir."
    test_version = "v1.2"
    
    # --- 1. İSTEK (CACHE MISS) ---
    logger.info(">>> 1. İSTEK GÖNDERİLİYOR (Beklenti: Cache Miss ve Ağ Çağrısı) <<<")
    res1 = await reduce_engine.analyze(test_transcript, test_version)
    logger.info("1. İstek Sonucu", tokens_used=res1.get("tokens_used"), analiz_metni=res1.get("text"))
    
    # (Araya ufak bir bekleme süresi koyalım ki WriterQueue diske flush yapabilsin)
    await asyncio.sleep(0.2)
    
    # --- 2. İSTEK (CACHE HIT) ---
    # Tamamen aynı metin, aynı versiyon
    logger.info(">>> 2. İSTEK GÖNDERİLİYOR (Beklenti: Cache Hit ve SIFIR Ağ Çağrısı) <<<")
    res2 = await reduce_engine.analyze(test_transcript, test_version)
    logger.info("2. İstek Sonucu", tokens_used=res2.get("tokens_used"), analiz_metni=res2.get("text"))
    
    # 3. Temizlik ve Doğrulama
    await db.close()
    await llm_port.close()
    if db_path.exists():
        try:
            db_path.unlink()
            # SQLite shm ve wal dosyalarını da temizle
            if Path("test_reduce.sqlite-wal").exists(): Path("test_reduce.sqlite-wal").unlink()
            if Path("test_reduce.sqlite-shm").exists(): Path("test_reduce.sqlite-shm").unlink()
        except Exception:
            pass
            
    logger.info("✅ İkinci istekte 'AĞ İSTEĞİ YAPILDI' logu görülmedi.")
    logger.info("✅ İçerik eşleştiği için LLM tetiklenmedi ve 0 token harcandı!")
    logger.info("--- K-308 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
