import sys
import os
import asyncio
import time
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.inference import InferencePort

logger = structlog.get_logger()

async def ping_loop(stop_event: asyncio.Event) -> float:
    """
    Ana event loop'ta her 100 ms'de bir uyanarak gecikmeyi ölçen heartbeat döngüsü.
    Eğer ana GIL kilitlenirse veya event loop boğulursa bu gecikme büyük ölçüde artar.
    """
    max_delay = 0.0
    interval = 0.1
    
    while not stop_event.is_set():
        start = time.perf_counter()
        await asyncio.sleep(interval)
        actual_delay = (time.perf_counter() - start) - interval
        
        # Sadece pozitif gecikmeleri say
        actual_delay = max(0, actual_delay)
        
        if actual_delay > max_delay:
            max_delay = actual_delay
            
        if actual_delay > 0.05: # Sadece belirgin (50 ms üstü) anlık sapmaları uyar
            logger.debug("ping_delay_detected", delay=round(actual_delay, 3))
            
    return max_delay

async def main() -> None:
    logger.info("--- M3 K-306: İŞLEM İZOLASYONU VE EVENT-LOOP GECİKME TESTİ ---")
    
    # CpuBudget=1 olarak InferencePort başlatılıyor
    port = InferencePort(max_workers=1)
    
    stop_event = asyncio.Event()
    
    # Ping döngüsünü arka planda başlat
    ping_task = asyncio.create_task(ping_loop(stop_event))
    
    logger.info("Ağır CPU işlemi (ProcessPool) başlatılıyor (Beklenen süre ~5 sn)...")
    logger.info("Eğer mimari yanlış olsaydı, önümüzdeki 5 saniye boyunca bu konsol donup kalırdı!")
    
    # Asenkron çıkarımı çalıştır (Ana loop bu sırada dönmeye devam edebiliyor mu ölçeceğiz)
    start_time = time.perf_counter()
    result = await port.run_inference("Dummy Video ID")
    total_time = time.perf_counter() - start_time
    
    logger.info("Çıkarım tamamlandı", sonuc=result, toplam_sure=round(total_time, 2))
    
    # İşlem bitti, sayaç döngüsünü durdur ve max gecikmeyi oku
    stop_event.set()
    max_delay: float = await ping_task
    
    logger.info("Event Loop Maksimum Gecikmesi", max_gecikme_sn=round(max_delay, 4))
    
    port.shutdown()
    
    # Hedef 100ms (0.1 sn). Windows uyku hassasiyet payıyla 0.15'i geçmemeli.
    assert max_delay < 0.15, f"Event loop çok fazla kilitlendi! Gecikme: {max_delay} sn"
    
    logger.info("✅ Gecikme eşiklerin altında. Event-loop GIL'den kurtarıldı ve asenkron akış güvende!")
    logger.info("--- K-306 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    # Windows'ta process spawn edilirken child process'ler main modülünü tekrar import eder
    # Bu yüzden multiprocessing kullanırken kodun if __name__ == "__main__": altında olması zorunludur.
    asyncio.run(main())
