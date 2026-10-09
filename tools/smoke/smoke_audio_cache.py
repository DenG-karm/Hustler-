import sys
import os
import asyncio
import structlog
import aiofiles

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.audio_cache import AudioCache

logger = structlog.get_logger()

# Test için API Maliyet Sayacı içeren Callback Simülasyonu
class MockTTSCallback:
    def __init__(self) -> None:
        self.api_call_count = 0
        
    async def generate_mock_audio(self, output_path: str) -> None:
        self.api_call_count += 1
        logger.warning(f"🌐 MOCK API ÇAĞRISI YAPILDI (Para Harcandı) | Toplam Çağrı: {self.api_call_count}")
        
        # Dosyayı fiziksel olarak diske yaz (Simülasyon)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(b"mock_audio_data_stream")

async def main() -> None:
    logger.info("--- M5 K-504: AUDIO CACHE (AKILLI ÖNBELLEK) TESTİ ---")
    
    # Test ortamı izolasyonu için geçici cache dizini
    test_cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', '.cache', 'test_audio')
    cache = AudioCache(cache_dir=test_cache_dir)
    api_mock = MockTTSCallback()
    
    test_text = "Bu metin önbelleğe alınacak ve bir daha asla API'ye gitmeyecek."
    voice_id = "deniz_voice_v1"
    
    # Temizlik (Önceki testlerden kalıntı kalmaması için cache dosyasını siliyoruz)
    cache_key = cache._generate_cache_key(test_text, voice_id)
    expected_file = os.path.join(test_cache_dir, f"{cache_key}.mp3")
    if os.path.exists(expected_file):
        os.remove(expected_file)
        
    # --- 1. İSTEK (CACHE MISS BEKLENİYOR) ---
    logger.info(">>> İLK İSTEK ATILIYOR <<<")
    result_path_1 = await cache.get_or_fetch(
        text=test_text, 
        voice_id=voice_id, 
        fetch_callback=api_mock.generate_mock_audio
    )
    
    # --- 2. İSTEK (CACHE HIT BEKLENİYOR) ---
    logger.info(">>> İKİNCİ İSTEK ATILIYOR (Birebir Aynı Metin) <<<")
    result_path_2 = await cache.get_or_fetch(
        text=test_text, 
        voice_id=voice_id, 
        fetch_callback=api_mock.generate_mock_audio
    )
    
    # --- DOĞRULAMALAR ---
    assert result_path_1 == result_path_2, "HATA: Önbellek, ilk dosyayı değil farklı bir yolu döndürdü!"
    assert os.path.exists(result_path_1), "HATA: Önbellek dosyası fiziksel olarak diske yazılmadı!"
    
    # En Kritik Doğrulama: Sadece 1 Kere API'ye (Callback) gitmiş olmalı
    assert api_mock.api_call_count == 1, f"KRİTİK HATA: API'ye {api_mock.api_call_count} kez gidildi! (Sadece 1 kez gidilmeliydi)"
    
    logger.info("✅ 1. İstek API'ye gitti ve diske yazıldı (Cache Miss).")
    logger.info("✅ 2. İstek API'ye GİTMEDEN doğrudan fiziksel diskten okundu (Cache Hit).")
    logger.info("✅ API Çağrı sayacı 1 olarak KESİN bir şekilde doğrulandı (Sıfır Ek Maliyet).")
    logger.info("--- K-504 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
