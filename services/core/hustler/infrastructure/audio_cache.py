import os
import hashlib
import structlog
from typing import Callable, Awaitable

logger = structlog.get_logger()

class AudioCache:
    """
    K-504: Akıllı Önbellek (Audio Cache) Mekanizması.
    Aynı metin ve aynı ses profili (voice_id) ile gelen TTS isteklerini 
    API'ye gitmeden doğrudan diskten okuyarak LLM/TTS maliyetlerini sıfırlar.
    """
    def __init__(self, cache_dir: str = ".cache/audio"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            
    def _generate_cache_key(self, text: str, voice_id: str) -> str:
        """
        Metin ve Voice ID'yi birleştirip normalize ederek
        deterministik (tekrar edilebilir) SHA-256 hash üretir.
        """
        normalized_text = text.strip().lower()
        # Hash çakışmasını (Collision) önlemek için araya benzersiz bir ayıraç (:::) koyuyoruz.
        raw_key = f"{voice_id}:::{normalized_text}"
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        
    async def get_or_fetch(self, text: str, voice_id: str, fetch_callback: Callable[[str], Awaitable[None]]) -> str:
        """
        Metin önbellekte varsa dosya yolunu döner (Cache Hit).
        Yoksa fetch_callback (API Adaptörü) aracılığıyla dosyayı üretir (Cache Miss).
        
        Args:
            fetch_callback: API'den veriyi çekip belirtilen (output_path) yoluna yazacak asenkron fonksiyon.
        """
        cache_key = self._generate_cache_key(text, voice_id)
        output_path = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        
        # Disk Kontrolü
        if os.path.exists(output_path):
            logger.info("Cache Hit (Önbellekten Okundu)", cache_key=cache_key[:8], voice_id=voice_id)
            return output_path
            
        logger.info("Cache Miss (API'ye Gidiliyor)", cache_key=cache_key[:8], voice_id=voice_id)
        
        # Callback'i (örn. ElevenLabs Adapter) tetikle ve dosyanın diske yazılmasını bekle
        await fetch_callback(output_path)
        
        # Fiziksel doğrulama (Callback sessizce çökerse veya dosyayı yaratmazsa engelle)
        if not os.path.exists(output_path):
            raise RuntimeError(f"KRİTİK HATA: Fetch Callback '{output_path}' dosyasını fiziksel olarak oluşturamadı!")
            
        return output_path
