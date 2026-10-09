import os
import hashlib
import asyncio
import httpx
import aiofiles
import structlog
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger()

class DownloadRetryError(Exception):
    """Ağ veya sunucu hatalarında yeniden deneme tetiklemek için kullanılan hata sınıfı."""
    pass

class AssetManager:
    """
    M6 K-602: Asset Manager
    Yüksek boyutlu medya dosyalarını RAM'i şişirmeden, chunk streaming yöntemiyle
    asenkron olarak diske yazar. Ağ kopmaları ve rate limit'lere karşı dirençlidir.
    """
    def __init__(self, download_dir: str = "downloads", max_concurrent: int = 5) -> None:
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        # Eşzamanlılık kısıtı (Concurrency Limit)
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def _generate_cache_key(self, url: str) -> str:
        """URL'den deterministik, benzersiz bir dosya adı (hash) üretir."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    @retry(
        stop=stop_after_attempt(4),  # İlk deneme + 3 retry
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(DownloadRetryError),
        reraise=True
    )
    async def _download_with_retry(self, client: httpx.AsyncClient, url: str, file_path: Path) -> Path:
        """Dosyayı aiter_bytes() ile parça parça çekip doğrudan diske yazar."""
        try:
            # Zaman aşımını büyük dosyalar için esnek tutuyoruz
            async with client.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
                # 429 ve 5xx hatalarında doğrudan retry tetikle
                if response.status_code == 429 or response.status_code >= 500:
                    logger.warning("Retry tetikleniyor: Sunucu hatası veya Rate Limit", 
                                   status_code=response.status_code, url=url)
                    raise DownloadRetryError(f"HTTP Error: {response.status_code}")
                
                # Diğer 4xx hatalarında doğrudan hata ver, retry yapma
                response.raise_for_status()

                # Bellek izolasyonu: 64KB'lık chunk'lar halinde diske akıt
                async with aiofiles.open(file_path, 'wb') as f:
                    chunk_count = 0
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        await f.write(chunk)
                        chunk_count += 1
                        
                logger.debug("Stream tamamlandı", url=url, chunk_count=chunk_count)
                return file_path
                
        except (httpx.RequestError, asyncio.TimeoutError) as e:
            # Ağ kopması, timeout gibi durumlarda retry tetikle
            logger.warning("Retry tetikleniyor: Ağ Hatası", error=str(e), url=url)
            raise DownloadRetryError(f"Network error: {str(e)}")

    async def download_asset(self, url: str, client: httpx.AsyncClient, ext: str = ".mp4") -> str:
        """
        URL'den medyayı indirir. Önbellekte varsa (Cache Hit) doğrudan döner.
        Yoksa Semaphore izni ile diske stream eder.
        """
        cache_key = self._generate_cache_key(url)
        
        # URL'den uzantı çıkartmayı dene, yoksa varsayılanı kullan
        url_ext = os.path.splitext(url)[1]
        final_ext = url_ext if url_ext and len(url_ext) <= 5 else ext
        
        file_name = f"{cache_key}{final_ext}"
        file_path = self.download_dir / file_name

        # Disk Önbelleği (Cache Hit) kontrolü
        if file_path.exists() and file_path.stat().st_size > 0:
            logger.info("Cache Hit: Dosya zaten diskte mevcut, ağ kullanılmadı.", path=str(file_path))
            return str(file_path)

        # Semaphore ile eşzamanlı istek kısıtı
        async with self.semaphore:
            logger.info("Semaphore izni alındı, indirme başlıyor.", url=url)
            try:
                await self._download_with_retry(client, url, file_path)
                logger.info("İndirme başarılı", path=str(file_path))
                return str(file_path)
            except Exception as e:
                logger.error("İndirme tamamen başarısız oldu", url=url, error=str(e))
                # Hatalı/yarım kalan dosyayı temizle
                if file_path.exists():
                    file_path.unlink()
                raise
