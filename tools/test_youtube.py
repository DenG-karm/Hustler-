import asyncio
import os
import re
import time
from typing import List

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

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

# Global metrik durumu
metrics = {
    "quota_used": 0,
    "rate_limit_errors": 0,
    "total_videos_fetched": 0,
}

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"


def parse_iso8601_duration(duration: str) -> int:
    """ISO 8601 süresini saniyeye çevirir (örn. PT59S -> 59, PT1M -> 60)."""
    pattern = re.compile(
        r"^PT"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?$"
    )
    match = pattern.match(duration)
    if not match:
        return 0

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    return hours * 3600 + minutes * 60 + seconds


def check_rate_limit(exception: BaseException) -> bool:
    """Sadece 403 ve 429 HTTP hatalarını tespit eder."""
    if isinstance(exception, httpx.HTTPStatusError):
        if exception.response.status_code in (403, 429):
            metrics["rate_limit_errors"] += 1
            return True
    return False


# 3. Direnç (Resilience): Üstel geri çekilme + Jitter
async def fetch_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """API isteklerini tenacity ile sarar, hata durumunda tekrar dener."""
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(httpx.HTTPStatusError) & retry_if_exception(check_rate_limit),
        wait=wait_random_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    ):
        with attempt:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
    # Bu return'e teorik olarak hiçbir zaman düşülmez (reraise=True)
    raise RuntimeError("Tenacity retry bloğu beklenmedik şekilde sonlandı.")


# 4. Search API Çağrısı
async def search_topic(client: httpx.AsyncClient, topic: str) -> List[str]:
    """Bir konu için max 20 adet short video arar."""
    logger.info("Search API cagiriliyor", topic=topic)
    params = {
        "part": "snippet",
        "type": "video",
        "videoDuration": "short",
        "maxResults": 20,
        "q": topic,
        "key": YOUTUBE_API_KEY,
    }
    
    try:
        response = await fetch_with_retry(client, "GET", f"{BASE_URL}/search", params=params)
        metrics["quota_used"] += 100
        data = response.json()
        video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
        logger.info("Search tamamlandi", topic=topic, found=len(video_ids))
        return video_ids
    except httpx.HTTPStatusError as e:
        logger.error("Search hatasi", topic=topic, status=e.response.status_code, error=str(e))
        return []


# 5. Videos API Çağrısı ve 6. Süre Doğrulaması
async def fetch_video_details(client: httpx.AsyncClient, video_ids: List[str]) -> None:
    """Video id'lerinin detaylarını çeker ve süreyi KATI bir şekilde doğrular."""
    if not video_ids:
        return
        
    ids_str = ",".join(video_ids)
    logger.info("Videos detaylari cekiliyor", batch_size=len(video_ids))
    params = {
        "part": "contentDetails,statistics",
        "id": ids_str,
        "key": YOUTUBE_API_KEY,
    }
    
    try:
        response = await fetch_with_retry(client, "GET", f"{BASE_URL}/videos", params=params)
        metrics["quota_used"] += 1
        data = response.json()
        items = data.get("items", [])
        
        for item in items:
            vid_id = item["id"]
            duration_iso = item.get("contentDetails", {}).get("duration", "")
            duration_sec = parse_iso8601_duration(duration_iso)
            
            # KATI DOĞRULAMA (Assert)
            try:
                assert duration_sec <= 60, f"Videonun ({vid_id}) süresi ({duration_sec}s), 60s sınırını aşıyor!"
                metrics["total_videos_fetched"] += 1
            except AssertionError as e:
                logger.error("Süre doğrulaması başarısız", video_id=vid_id, duration_iso=duration_iso, error=str(e))
                
        logger.info("Videos detayi tamamlandi", valid_count=len(items))
    except httpx.HTTPStatusError as e:
        logger.error("Videos detayi hatasi", status=e.response.status_code, error=str(e))


async def main():
    if not YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY çevre değişkeni bulunamadı. Script sonlandırılıyor.")
        return

    topics = ["psikoloji", "finans", "fitness", "teknoloji", "tarih"]
    start_time = time.time()
    
    logger.info("M1 Faz 0 Doğrulama Testi: YouTube Data API Asenkron Çekimi", topics=topics)
    
    # 2. Asenkron HTTP İstemcisi oluşturulması
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Konuları eşzamanlı olarak arat
        search_tasks = [search_topic(client, topic) for topic in topics]
        search_results = await asyncio.gather(*search_tasks)
        
        # Benzersiz Video ID'lerini topla
        all_video_ids = set()
        for res in search_results:
            all_video_ids.update(res)
            
        all_video_ids = list(all_video_ids)
        logger.info("Toplam benzersiz short videoları bulundu", count=len(all_video_ids))
        
        import json
        with open(os.path.join(os.path.dirname(__file__), "video_ids.json"), "w", encoding="utf-8") as f:
            json.dump(all_video_ids, f)
        
        # API Kota optimizasyonu için 50'şerli gruplara ayır
        batch_size = 50
        batches = [all_video_ids[i:i + batch_size] for i in range(0, len(all_video_ids), batch_size)]
        
        # Tüm grupları eşzamanlı detaylandır
        detail_tasks = [fetch_video_details(client, batch) for batch in batches]
        await asyncio.gather(*detail_tasks)

    elapsed_time = time.time() - start_time
    
    # 7. Metrik Çıktısı 
    # structlog.dev.ConsoleRenderer ile anahtarlar formunda formatlı / tabloyu andıran çıktı.
    logger.info(
        "=== TEST METRİKLERİ VE SONUÇ ÖZETİ ===",
        total_time_seconds=round(elapsed_time, 2),
        total_fetched_videos=metrics["total_videos_fetched"],
        total_quota_used=metrics["quota_used"],
        rate_limit_errors_caught=metrics["rate_limit_errors"],
    )


if __name__ == "__main__":
    asyncio.run(main())
