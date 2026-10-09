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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.orchestration.map_b import MapBExecutor
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse

logger = structlog.get_logger()

# Test için API çağrısını mockluyoruz (Network Rate-Limit yememek ve süreci hızlandırmak için)
async def mock_execute(prompt: str) -> LLMResponse:
    if "FAIL_ME" in prompt:
        raise ValueError("Bilinçli Kısmi Başarısızlık Testi (Simülasyon)")
    # API ağ gecikmesi simülasyonu (0.5 saniye)
    await asyncio.sleep(0.5)
    return LLMResponse("Sentetik Analiz Sonucu (Kanca bulundu: Evet)", 50, 50, 100)

async def main() -> None:
    logger.info("--- M3 K-307: MAP B ÇALIŞTIRICI (EXECUTOR) TESTİ ---")
    
    # 1. LLMPort'u limitsiz tokenla ve ağ korumalı olarak mockla
    llm_port = LLMPort(api_key="MOCK_KEY", max_tokens=999999)
    setattr(llm_port, "_execute_network_request", mock_execute)
    
    # 2. Çalıştırıcıyı (Executor) örnekle
    executor = MapBExecutor(llm_port=llm_port)
    
    # 3. 20 adet Sentetik Video Datası Hazırla
    videos = []
    for i in range(1, 21):
        # 13. videoya kasıtlı olarak "FAIL_ME" veriyoruz
        vid_id = f"vid_{i:02d}"
        transcript = "FAIL_ME" if i == 13 else f"Bu {i}. videonun transkript içeriği..."
        videos.append({"video_id": vid_id, "transcript": transcript})
        
    logger.info("20 video Map B (API Modu - Semaphor 5) kuyruğuna gönderiliyor...")
    
    start_time = time.perf_counter()
    
    # 4. Yığın (Batch) Analiz Başlat
    results = await executor.execute_batch(videos, use_local_model=False)
    
    duration = time.perf_counter() - start_time
    
    # 5. Metrikleri Topla
    success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
    error_count = sum(1 for r in results if r.get("status") == "FAILED")
    
    logger.info("=== MAP B ÇALIŞTIRICI ÖZETİ ===",
        toplam_video=len(videos),
        basarili_islem=success_count,
        hatali_islem=error_count,
        toplam_sure_sn=round(duration, 2)
    )
    
    # 6. Doğrulamalar (Çıkış Kriterleri)
    assert success_count == 19, f"Kısmi başarısızlık izolasyonu bozuk! 19 başarılı bekleniyordu, {success_count} geldi."
    assert error_count == 1, f"Kısmi başarısızlık izolasyonu bozuk! 1 hata bekleniyordu, {error_count} geldi."
    
    # Eğer Semaphore çalışmasaydı 20 * 0.5 = 10 saniye sürerdi (Senkron olsa).
    # Sınırsız paralellik olsa 0.5 saniye sürerdi.
    # Semaphore=5 olduğu için her turda 5 iş biter. Toplam 4 tur (4 x 0.5s = 2s civarı) sürmeli.
    assert duration < 60, f"Performans bariyeri aşıldı! Süre {duration} > 60 sn"
    
    logger.info("✅ Kısmi Başarısızlık (Partial Failure) başarıyla izole edildi. 1 Hata diğer 19 işlemi BOZAMADI.")
    logger.info(f"✅ İşlem süresi ({duration:.2f}sn) 60 saniye bariyerinin çok çok altında.")
    
    await llm_port.close()
    logger.info("--- K-307 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
