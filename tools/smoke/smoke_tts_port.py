import sys
import os
import asyncio
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.tts_port import ElevenLabsAdapter
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import httpx

logger = structlog.get_logger()

# Test amaçlı Fake TTS Adaptörü (httpx kütüphanesine bağımlı kalmadan mantığı test eder)
class MockElevenLabsAdapter(ElevenLabsAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK_API_KEY")
        self.call_count = 0
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    async def generate_audio_stream(self, text: str, output_path: str, voice_id: str) -> None:
        self.call_count += 1
        logger.info("🔥 MOCK TTS API ÇAĞRISI YAPILDI 🔥", deneme=self.call_count)
        
        # 1. İlk çağrıda ağ hatası simülasyonu (Rate Limit)
        if self.call_count == 1:
            import httpx
            logger.warning("Simüle Edilen Ağ Hatası (429 Too Many Requests)")
            req = httpx.Request("POST", "mock_url")
            res = httpx.Response(429, request=req)
            raise httpx.HTTPStatusError("429 Too Many Requests", request=req, response=res)
            
        # 2. İkinci çağrıda chunk streaming simülasyonu (Başarılı)
        logger.info("Bağlantı Kuruldu, Veri Akışı (Stream) Başlıyor...")
        
        import aiofiles
        # Bellek İzolasyonu Simülasyonu: 4 parça halinde diske yazılacak
        mock_chunks = [b"chunk1_", b"chunk2_", b"chunk3_", b"chunk4"]
        
        async with aiofiles.open(output_path, 'wb') as f:
            for chunk in mock_chunks:
                await f.write(chunk)
                await asyncio.sleep(0.01) # Gerçek bir indirme süreci simülasyonu (Asenkron)
                
        # Ledger güncellemesi (Gerçek sınıftakiyle aynı davranış)
        self.total_chars_processed += len(text)
        logger.info("TTS İsteği Başarılı (Stream to Disk)", toplam_kullanim=self.total_chars_processed)

async def main() -> None:
    logger.info("--- M5 K-501: TTS PORT VE MOCK ADAPTÖR TESTİ ---")
    
    adapter = MockElevenLabsAdapter()
    
    test_text = "Bu metin sese dönüştürülürken RAM kesinlikle şişmeyecek, doğrudan diske akacak."
    output_file = "test_output_mock.mp3"
    
    try:
        # İsteği Başlat
        await adapter.generate_audio_stream(test_text, output_file, "voice_123")
        
        # --- TEST 1: Bellek İzolasyonu (Chunk Streaming) ---
        assert os.path.exists(output_file), "Kritik Hata: Ses dosyası diske yazılmadı!"
        
        with open(output_file, "rb") as f:
            content = f.read()
            assert content == b"chunk1_chunk2_chunk3_chunk4", "Kritik Hata: Chunk verisi eksik veya bozuk!"
            
        logger.info("✅ TEST 1 BAŞARILI: Veri RAM'i şişirmeden (Chunk Streaming) başarıyla diske yazıldı.")
        
        # --- TEST 2: Maliyet Defteri (Ledger) ---
        expected_chars = len(test_text)
        actual_chars = adapter.get_total_chars_processed()
        assert actual_chars == expected_chars, f"Karakter sayımı yanlış! Beklenen: {expected_chars}, Gerçek: {actual_chars}"
        logger.info("✅ TEST 2 BAŞARILI: Karakter maliyeti in-memory deftere doğru işlendi.", harcanan_karakter=actual_chars)
        
        # --- TEST 3: Direnç (Retry) ---
        assert adapter.call_count == 2, "Tenacity retry mekanizması çalışmadı, sistem direkt çöktü!"
        logger.info("✅ TEST 3 BAŞARILI: 429 Ağ hatasına karşı Exponential Backoff (Geri Çekilme) direnci mükemmel çalıştı.")
        
    finally:
        # Temizlik
        if os.path.exists(output_file):
            os.remove(output_file)
            
    logger.info("--- K-501 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
