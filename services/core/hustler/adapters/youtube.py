import httpx
from typing import Optional, AsyncGenerator, Any
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)
import structlog
from services.core.hustler.storage.cache import YouTubeCache

logger = structlog.get_logger()

def check_rate_limit(exception: BaseException) -> bool:
    """Sadece Rate Limit ve yetki hatalarını (403, 429) yakalar."""
    if isinstance(exception, httpx.HTTPStatusError):
        if exception.response.status_code in (403, 429):
            return True
    return False


class YouTubeClient:
    def __init__(self, api_key: str, cache: Optional[YouTubeCache] = None):
        self.api_key = api_key
        self.cache = cache
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self._client: Optional[httpx.AsyncClient] = None
        self.quota_used = 0

    async def __aenter__(self) -> "YouTubeClient":
        """Asenkron bağlam (async context manager) desteği"""
        self._client = httpx.AsyncClient(timeout=15.0)
        return self
        
    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if self._client:
            await self._client.aclose()

    async def _fetch_with_retry(self, method: str, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Cache denetimli ve Tenacity backoff mekanizmalı API Çağrısı"""
        
        # 1. Önbellek kontrolü
        cache_key = f"{url}?{str(sorted(params.items()))}"
        if self.cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                logger.info("API İsteği Atlandı (Cache Hit)", url=url)
                return cached_data

        # 2. Ağ İsteği Hazırlığı
        req_params = params.copy()
        req_params["key"] = self.api_key
        
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(httpx.HTTPStatusError) & retry_if_exception(check_rate_limit),
            wait=wait_random_exponential(multiplier=1, min=1, max=10),
            stop=stop_after_attempt(5),
            reraise=True,
        ):
            with attempt:
                if not self._client:
                    raise RuntimeError("YouTubeClient context manager dışında kullanıldı ('with' bloku yok).")
                    
                response = await self._client.request(method, url, params=req_params)
                response.raise_for_status()
                data = response.json()
                
                # Kota tüketimi güncellemesi
                if "search" in url:
                    self.quota_used += 100
                elif "videos" in url:
                    self.quota_used += 1
                else:
                    self.quota_used += 1
                    
                # Sonucu Cache'e yaz (API key içermeyen orjinal params üzerinden üretilen key ile)
                if self.cache:
                    await self.cache.set(cache_key, data)
                    
                return dict(data) if isinstance(data, dict) else {}
        
        raise RuntimeError("Tenacity beklenmedik şekilde sonlandı.")

    async def search_shorts(self, topic: str, max_results: int = 40) -> AsyncGenerator[dict[str, Any], None]:
        """Arama için sayfalama (pagination) mantığı. Shorts'ları sayfa sayfa yield eder."""
        url = f"{self.base_url}/search"
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "videoDuration": "short",
            "q": topic,
        }
        
        fetched = 0
        while fetched < max_results:
            # maxResults API sınırı 50'dir.
            params["maxResults"] = min(max_results - fetched, 50)
            
            data = await self._fetch_with_retry("GET", url, params)
            items = data.get("items", [])
            
            for item in items:
                yield item
                fetched += 1
                if fetched >= max_results:
                    break
                    
            next_token = data.get("nextPageToken")
            if not next_token or not items:
                break
            params["pageToken"] = next_token

    async def get_videos_details(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Detay end-pointi (50'şerli batching ile sayfalama mantığı)."""
        url = f"{self.base_url}/videos"
        results = []
        batch_size = 50
        
        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i:i + batch_size]
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(batch)
            }
            data = await self._fetch_with_retry("GET", url, params)
            results.extend(data.get("items", []))
            
        return results
