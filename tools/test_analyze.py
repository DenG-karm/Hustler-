from typing import Any
import asyncio
import json
import random
import time

import structlog
from pydantic import BaseModel, ValidationError

# --- LOGGING KURULUMU ---
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


# =====================================================================
# GÖREV 1: LLM Şema Uyumu ve Map-Reduce (K-103)
# =====================================================================

class SummaryCard(BaseModel):
    video_id: str
    kanca_turu: str
    ana_fikir: str
    token_sayisi: int


class MockLLMAdapter:
    def __init__(self) -> None:
        self.total_tokens = 0
        self.call_count = 0

    async def generate_summary(self, video_id: str) -> str:
        """Sahte LLM Çağrısı: Rastgele %10 ihtimalle eksik/hatalı JSON döner."""
        await asyncio.sleep(0.05)  # Ağ gecikmesi simülasyonu
        tokens_used = random.randint(150, 250)
        
        self.total_tokens += tokens_used
        self.call_count += 1

        # Deterministik %10 hata oranı (her 10. çağrıda kırık JSON)
        if self.call_count % 10 == 0:
            return '{"video_id": "' + video_id + '", "kanca_turu": "EksikJSON' 
        
        return json.dumps({
            "video_id": video_id,
            "kanca_turu": "Soru Kancası",
            "ana_fikir": "İzleyicinin dikkatini çekecek psikolojik bir olguyu açıklamak.",
            "token_sayisi": tokens_used
        })

llm_metrics = {
    "first_try_success": 0,
    "retry_success": 0,
    "failed": 0,
}

async def map_phase_task(video_id: str, adapter: MockLLMAdapter, semaphore: asyncio.Semaphore) -> Any:
    """Eşzamanlı Map aşaması ve Validation Error Retry (Maks 2)"""
    async with semaphore:
        for attempt in range(3):  # 1 ilk deneme + 2 retry
            try:
                response = await adapter.generate_summary(video_id)
                data = json.loads(response)
                card = SummaryCard(**data)
                
                if attempt == 0:
                    llm_metrics["first_try_success"] += 1
                else:
                    llm_metrics["retry_success"] += 1
                return card
            
            except (json.JSONDecodeError, ValidationError):
                logger.debug("LLM Şema Hatası, Retry tetikleniyor", video_id=video_id, attempt=attempt+1)
                if attempt == 2:
                    llm_metrics["failed"] += 1
                    logger.error("LLM Çağrısı Başarısız (Tüm Retry'lar tükendi)", video_id=video_id)
                    return None

async def run_llm_test() -> None:
    logger.info("--- GÖREV 1: LLM Şema Uyumu ve Map-Reduce Testi ---")
    adapter = MockLLMAdapter()
    semaphore = asyncio.Semaphore(5)
    
    videos = [f"vid_{i:03d}" for i in range(30)]
    tasks = [map_phase_task(vid, adapter, semaphore) for vid in videos]
    
    await asyncio.gather(*tasks)
    
    first_try_rate = (llm_metrics["first_try_success"] / 30) * 100
    total_success = llm_metrics["first_try_success"] + llm_metrics["retry_success"]
    final_success_rate = (total_success / 30) * 100
    
    logger.info(
        "LLM Map-Reduce Sonuçları",
        ilk_deneme_basarisi=f"%{first_try_rate:.1f}",
        nihai_basari=f"%{final_success_rate:.1f}",
        toplam_token_maliyeti=adapter.total_tokens
    )
    
    # Assertions
    assert first_try_rate >= 85.0, f"İlk deneme başarısı beklenen oranın altında: %{first_try_rate}"
    assert final_success_rate == 100.0, "Yeniden denemeler sonrası başarı %100 olmalıydı!"
    logger.info("GÖREV 1 BAŞARILI.")


# =====================================================================
# GÖREV 2: CPU Darboğazı ve Devre Kesici (K-106)
# =====================================================================

class CircuitBreakerOpenError(Exception):
    pass

class CircuitBreaker:
    def __init__(self, max_consecutive: int=5, max_time_budget: float=10.0) -> None:
        self.max_consecutive = max_consecutive
        self.max_time_budget = max_time_budget
        
        self.consecutive_count = 0
        self.total_time_spent = 0.0
        self.is_open = False

    def record_usage(self, duration: float) -> None:
        if self.is_open:
            return
            
        self.consecutive_count += 1
        self.total_time_spent += duration
        
        # Sınır aşılırsa devre kesici AÇILIR (Open state)
        if self.consecutive_count >= self.max_consecutive or self.total_time_spent >= self.max_time_budget:
            self.is_open = True
            logger.warning("DEVRE KESİCİ AÇILDI (OPEN)", reason="Limit Aşıldı", count=self.consecutive_count, time=round(self.total_time_spent, 2))

    def check(self) -> None:
        if self.is_open:
            raise CircuitBreakerOpenError("Devre Kesici AÇIK. Yeni işlem reddedildi.")


def synthetic_cpu_heavy_task(duration_sec: float) -> float:
    """Event loop'u bloklama potansiyeli olan sentetik CPU ağır işlem (Whisper simülasyonu)."""
    start = time.time()
    while time.time() - start < duration_sec:
        _ = sum(i * i for i in range(5000))
    return time.time() - start


async def process_transcript(video_id: str, cb: CircuitBreaker) -> str:
    try:
        cb.check()
    except CircuitBreakerOpenError as e:
        logger.debug("İşlem reddedildi", video_id=video_id, error=str(e))
        return "REJECTED"
        
    start = time.perf_counter()
    # Ortalama 2.1 saniyelik ağır CPU yükü (5 işlemde ~10.5 saniye ile limiti patlatır)
    await asyncio.to_thread(synthetic_cpu_heavy_task, 2.1)
    elapsed = time.perf_counter() - start
    
    cb.record_usage(elapsed)
    return "PROCESSED"

cb_metrics = {
    "max_delay_ms": 0.0
}

async def event_loop_monitor() -> None:
    """Arka planda çalışarak event loop gecikmesini ölçer (Bloklanmayı tespit eder)."""
    while True:
        start = time.perf_counter()
        await asyncio.sleep(0.05)  # 50ms bekle
        delay = (time.perf_counter() - start - 0.05) * 1000
        if delay > cb_metrics["max_delay_ms"]:
            cb_metrics["max_delay_ms"] = delay
        if cb_metrics["max_delay_ms"] > 1000:
            break


async def run_circuit_breaker_test() -> None:
    logger.info("--- GÖREV 2: CPU Darboğazı ve Devre Kesici Testi ---")
    cb = CircuitBreaker(max_consecutive=5, max_time_budget=10.0)
    
    monitor_task = asyncio.create_task(event_loop_monitor())
    videos = [f"trans_vid_{i:02d}" for i in range(8)]
    
    # İşlemler asenkron olarak bekletilip çalıştırılır
    for vid in videos:
        await process_transcript(vid, cb)
    
    monitor_task.cancel()
    
    logger.info(
        "Devre Kesici Sonuçları",
        is_open=cb.is_open,
        toplam_islem_suresi=round(cb.total_time_spent, 2),
        islenen_video_sayisi=cb.consecutive_count,
        event_loop_max_gecikme_ms=round(cb_metrics["max_delay_ms"], 2)
    )
    
    # Assertions
    assert cb.is_open, "Devre Kesici beklenen sınırda açılmadı!"
    assert cb_metrics["max_delay_ms"] < 100.0, f"Event loop bloklandı! Gecikme: {cb_metrics['max_delay_ms']:.2f}ms"
    logger.info("GÖREV 2 BAŞARILI.")


async def main() -> None:
    await run_llm_test()
    print("\n" + "="*50 + "\n")
    await run_circuit_breaker_test()

if __name__ == "__main__":
    asyncio.run(main())
