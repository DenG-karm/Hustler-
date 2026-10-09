import sys
import os
import asyncio
import structlog
import httpx
import time
from pathlib import Path
from typing import Any

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.asset_manager import AssetManager

logger = structlog.get_logger()

# Aktif indirme sayısını takip edip semaphore'un 5'i geçmediğini kanıtlamak için sayaç
class ConcurrencyTracker:
    def __init__(self) -> None:
        self.active_downloads = 0
        self.max_observed = 0
        self.lock = asyncio.Lock()

    async def start_download(self) -> None:
        async with self.lock:
            self.active_downloads += 1
            if self.active_downloads > self.max_observed:
                self.max_observed = self.active_downloads
            logger.debug("Bağlantı açıldı", aktif_istek=self.active_downloads)

    async def end_download(self) -> None:
        async with self.lock:
            self.active_downloads -= 1
            logger.debug("Bağlantı kapandı", aktif_istek=self.active_downloads)

tracker = ConcurrencyTracker()

# Mock httpx.AsyncClient'ın stream fonksiyonu
class MockResponse:
    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Mock Error", request=httpx.Request("GET", self.url), response=httpx.Response(self.status_code, request=httpx.Request("GET", self.url)))

    async def aiter_bytes(self, chunk_size: int = 65536) -> Any:
        # 10 Chunk (Toplam ~650KB) medya simülasyonu
        for i in range(10):
            await asyncio.sleep(0.05) # I/O ve ağ gecikmesi
            yield b"1" * chunk_size

class MockStreamContext:
    def __init__(self, url: str, attempt_counter: dict[str, int]) -> None:
        self.url = url
        self.attempt_counter = attempt_counter

    async def __aenter__(self) -> MockResponse:
        await tracker.start_download()
        
        # Eğer fail simülasyonu URL'siyse, ilk 2 denemede 500 dönsün, 3'te başarsın
        if "fail_test" in self.url:
            self.attempt_counter[self.url] = self.attempt_counter.get(self.url, 0) + 1
            if self.attempt_counter[self.url] <= 2:
                return MockResponse(500, self.url)
            else:
                return MockResponse(200, self.url)
        
        return MockResponse(200, self.url)

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await tracker.end_download()

from unittest.mock import patch

def mock_stream_factory(method: str, url: str, **kwargs: Any) -> MockStreamContext:
    # URL'den domain'i kesip asıl test isimlerini alabiliriz ama basitçe kwargs'ı ignore ediyoruz
    return MockStreamContext(str(url), ATTEMPT_COUNTER)

ATTEMPT_COUNTER: dict[str, int] = {}

async def main() -> None:
    logger.info("--- M6 K-602: ASSET MANAGER (MEDYA YÖNETİCİSİ) TESTİ ---")
    
    # downloads klasörünü temizle
    download_dir = Path("test_downloads")
    if download_dir.exists():
        for file in download_dir.glob("*"):
            file.unlink()
            
    manager = AssetManager(download_dir=str(download_dir), max_concurrent=5)
    
    # 9 adet normal medya URL'si ve 1 adet direnç testi (fail_test) URL'si
    urls = [f"https://example.com/media/video_{i}.mp4" for i in range(9)]
    urls.append("https://example.com/media/fail_test_retry.mp4")
    
    client = httpx.AsyncClient()
    patcher = patch.object(client, 'stream', side_effect=mock_stream_factory)
    patcher.start()
    
    start_time = time.time()
    
    # 1. GÖREV: 10 dosyayı Asenkron Olarak Başlat (Concurrency & Chunk Streaming Testi)
    logger.info("10 yüksek boyutlu medya asenkron indirilmeye başlanıyor...")
    tasks = []
    for url in urls:
        tasks.append(manager.download_asset(url, client, ext=".mp4"))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Tüm indirmeler tamamlandı", gecen_sure=round(time.time() - start_time, 2))
    
    # Semaphore Limit Testi Sonucu
    logger.info("Eşzamanlılık Kısıtı (Semaphore) Sonucu", maksimum_aktif_istek=tracker.max_observed)
    assert tracker.max_observed <= 5, f"HATA: Semaphore limitini aştı! Maks: {tracker.max_observed}"
    
    # Direnç Testi Sonucu (Retry)
    fail_url = "https://example.com/media/fail_test_retry.mp4"
    retry_count = ATTEMPT_COUNTER.get(fail_url, 0)
    logger.info("Direnç Mekanizması (Retry) Sonucu", hata_alan_url=fail_url, toplam_deneme_sayisi=retry_count)
    assert retry_count == 3, f"HATA: Beklenen deneme sayısı 3, ancak {retry_count} yapıldı!"
    
    # Disk Cache Hit Testi
    logger.info(">>> Cache Hit (Önbellek) Testi Başlıyor <<<")
    # Aynı url listesinden birini tekrar isteyelim
    cache_url = urls[0]
    cached_path = await manager.download_asset(cache_url, client, ext=".mp4")
    logger.info("Cache Hit Testi Tamamlandı", donen_path=cached_path)
    
    # Temizlik
    for file in download_dir.glob("*"):
        file.unlink()
    download_dir.rmdir()
    
    logger.info("--- K-602 TESTİ BAŞARIYLA TAMAMLANDI ---")

if __name__ == '__main__':
    asyncio.run(main())
