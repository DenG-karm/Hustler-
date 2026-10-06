import asyncio
import structlog
from youtube_transcript_api import YouTubeTranscriptApi

# 1. Ortam ve Loglama Kurulumu
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20), # 20 is logging.INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

import json
import os

# 1. Girdi Verisi: test_youtube.py çıktısından okunan gerçek ID'ler.
ids_path = os.path.join(os.path.dirname(__file__), "video_ids.json")
try:
    with open(ids_path, "r", encoding="utf-8") as f:
        VIDEO_IDS = json.load(f)
except FileNotFoundError:
    logger.error("video_ids.json bulunamadı. Lütfen önce test_youtube.py'yi çalıştırın.")
    VIDEO_IDS = []

# 2. Eşzamanlılık Kontrolü (IP Koruması)
# Aynı anda en fazla 10 isteğe izin veren Semaphore
CONCURRENCY_LIMIT = 10
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Test metrikleri
metrics = {
    "total_tested": 0,
    "yerlesik_altyazi_var": 0,
    "whisper_icin_isaretlendi": 0,
}


def fetch_transcript_metadata_sync(video_id: str) -> bool:
    """
    youtube-transcript-api senkron çalışır. Bu fonksiyon sadece meta veri listesi çeker.
    Videoyu indirmez, API üzerinden meta veride altyazı olup olmadığına bakar.
    """
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        # Herhangi bir dilde altyazı listesi başarıyla çekilirse True
        return True
    
    # 4. Hata Yönetimi (Kısmi Başarısızlık)
    except Exception as e:
        err_name = e.__class__.__name__
        if err_name in ("TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable", "NoTranscriptAvailable"):
            logger.debug("Altyazı veya video bulunamadı", video_id=video_id, error=err_name)
            return False
        elif err_name in ("TooManyRequests", "YouTubeRequestFailed"):
            logger.warning("YouTube API İsteği Başarısız (Rate Limit/Network)", video_id=video_id, error=err_name)
            return False
        else:
            logger.error("Bilinmeyen Hata", video_id=video_id, error=str(e), err_type=err_name)
            return False


async def check_transcript_async(video_id: str):
    """
    Her video için Semafor üzerinden geçen ve event loop'u bloklamayan wrapper.
    """
    async with semaphore:
        # 3. Asenkron Wrapper
        has_transcript = await asyncio.to_thread(fetch_transcript_metadata_sync, video_id)
        
        metrics["total_tested"] += 1
        
        # 5. Durum Sınıflandırması
        if has_transcript:
            metrics["yerlesik_altyazi_var"] += 1
            logger.debug("Durum: Yerlesik_Altyazi_Var", video_id=video_id)
        else:
            metrics["whisper_icin_isaretlendi"] += 1
            logger.debug("Durum: Whisper_Icin_Isaretlendi", video_id=video_id)


async def main():
    logger.info("M1 Faz 0 Doğrulama Testi: Transcript Kapsama Ölçümü Başlatılıyor", concurrency_limit=CONCURRENCY_LIMIT)
    
    # Tüm videolar için asenkron task listesi oluştur
    tasks = [check_transcript_async(vid) for vid in VIDEO_IDS]
    
    # Tüm görevleri eşzamanlı olarak (Semafor kısıtlamasıyla) çalıştır
    await asyncio.gather(*tasks)
    
    # 6. Raporlama
    total = metrics["total_tested"]
    has_sub = metrics["yerlesik_altyazi_var"]
    needs_whisper = metrics["whisper_icin_isaretlendi"]
    
    coverage_rate = (has_sub / total * 100) if total > 0 else 0
    
    logger.info(
        "=== TRANSCRIPT KAPSAMA TEST METRİKLERİ ===",
        total_tested=total,
        yerlesik_altyazi_var=has_sub,
        whisper_icin_isaretlendi=needs_whisper,
        kapsama_orani_yuzde=round(coverage_rate, 2)
    )
    
    if coverage_rate >= 90:
        logger.info("TEST BAŞARILI", detail="Kapsama oranı %90 hedefini karşılıyor.")
    else:
        logger.warning("KAPSAMA YETERSİZ", detail="Kapsama oranı %90 hedefini karşılamıyor, Whisper devre kesici yükü artabilir.")


if __name__ == "__main__":
    asyncio.run(main())
