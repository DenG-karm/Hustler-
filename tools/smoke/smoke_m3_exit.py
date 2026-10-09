import sys
import os
import asyncio
import time
import structlog
from pathlib import Path

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.infrastructure.inference import InferencePort
from services.core.hustler.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError
from services.core.hustler.orchestration.map_b import MapBExecutor
from services.core.hustler.orchestration.reduce import ReduceOrchestrator

logger = structlog.get_logger()

# Test Mocks
async def mock_llm_execute(prompt: str) -> LLMResponse:
    # 0.5sn ağ gecikmesi simülasyonu
    await asyncio.sleep(0.5)
    return LLMResponse("Analiz sonucu OK", 50, 50, 100)

async def ping_loop(stop_event: asyncio.Event) -> float:
    max_delay = 0.0
    interval = 0.1
    while not stop_event.is_set():
        start = time.perf_counter()
        await asyncio.sleep(interval)
        actual_delay = max(0, (time.perf_counter() - start) - interval)
        if actual_delay > max_delay:
            max_delay = actual_delay
    return max_delay

async def main() -> None:
    logger.info("=========================================")
    logger.info("   M3 ÇIKIŞ KRİTERLERİ (EXIT CRITERIA)   ")
    logger.info("=========================================")

    # Test DB Hazırlığı
    db_path = Path("m3_exit.sqlite")
    if db_path.exists():
        try: db_path.unlink()
        except: pass
    
    db = Database(db_path)
    await db.init()

    # --- [ADIM 1 & 2] PERFORMANS VE MALİYET KORUMASI (20 Video) ---
    logger.info("--- [ADIM 1 & 2] 20 VİDEO UÇTAN UCA İŞLEM ---")
    
    # 5000 Token Bütçesi
    llm_port = LLMPort(api_key="MOCK", max_tokens=5000)
    setattr(llm_port, "_execute_network_request", mock_llm_execute)
    
    reduce_engine = ReduceOrchestrator(db, llm_port)
    await reduce_engine.init_table()
    
    executor = MapBExecutor(llm_port=llm_port)
    
    # 20 video verisi
    videos = [{"video_id": f"vid_{i}", "transcript": f"Video transkript içeriği {i}"} for i in range(1, 21)]
        
    start_time = time.perf_counter()
    
    # 1. Map Katmanı (Yığın halinde 5'li eşzamanlı)
    await executor.execute_batch(videos, use_local_model=False)
    
    # 2. Reduce Katmanı (Kalıcı Önbelleğe yazma)
    for v in videos:
        await reduce_engine.analyze(v["transcript"], "v1.0")
        
    duration = time.perf_counter() - start_time
    total_tokens = llm_port.ledger.current_usage
    
    logger.info(f"Performans Süresi: {duration:.2f} saniye (Hedef < 180s)")
    logger.info(f"Toplam LLM Maliyeti: {total_tokens} token (Hedef < 5000)")
    
    assert duration < 180, f"Performans patladı! {duration} sn > 180 sn"
    assert total_tokens <= 5000, f"Bütçe aşıldı! {total_tokens} > 5000"

    # --- [ADIM 3] DEVRE KESİCİ TESTİ ---
    logger.info("--- [ADIM 3] DEVRE KESİCİ TESTİ (CUDA=False SIMULATION) ---")
    
    circuit_config = CircuitBreakerConfig(max_consecutive_failures=3, cooldown_seconds=2)
    breaker = CircuitBreaker("Local-CPU-Model", config=circuit_config)
    
    # 4 kez hata fırlatmayı dene (CUDA yokken CPU OOM gibi durumlar)
    for i in range(4):
        try:
            async with breaker:
                raise ValueError("Donanım yetersiz: OOM hatası!")
        except Exception as e:
            if isinstance(e, CircuitBreakerOpenError):
                logger.info("✅ Devre Kesici başarıyla tetiklendi ve sistemi kitlenmekten kurtardı (Fail-Fast)!")
                break
            
    assert breaker.state.value == "OPEN", "Devre kesici AÇIK duruma geçemedi!"

    # --- [ADIM 4] EVENT LOOP DİRENCİ (Ağır İşlem Altında) ---
    logger.info("--- [ADIM 4] EVENT LOOP DİRENCİ (GİL İZOLASYON TESTİ) ---")
    
    inference_port = InferencePort(max_workers=1)
    stop_event = asyncio.Event()
    ping_task = asyncio.create_task(ping_loop(stop_event))
    
    logger.info("Yerel ağır CPU çıkarımı başlatılıyor (Beklenen süre ~5 sn)...")
    await inference_port.run_inference("Test Video")
    
    stop_event.set()
    max_delay: float = await ping_task
    
    inference_port.shutdown()
    
    logger.info(f"Maksimum Event Loop Gecikmesi: {max_delay:.4f} saniye (Hedef < 0.15s)")
    assert max_delay < 0.15, f"Event loop çok yavaşladı: {max_delay} sn"

    # Temizlik
    await db.close()
    await llm_port.close()
    if db_path.exists():
        try:
            db_path.unlink()
            if Path("m3_exit.sqlite-wal").exists(): Path("m3_exit.sqlite-wal").unlink()
            if Path("m3_exit.sqlite-shm").exists(): Path("m3_exit.sqlite-shm").unlink()
        except:
            pass

    logger.info("=========================================")
    logger.info("✅ M3 ÇIKIŞ KRİTERLERİ TAMAMEN SAĞLANDI! ✅")
    logger.info("=========================================")

if __name__ == "__main__":
    asyncio.run(main())
