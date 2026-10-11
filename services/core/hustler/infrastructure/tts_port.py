import abc
import base64
import binascii
import json
import httpx
import structlog
import aiofiles
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming
from services.core.hustler.infrastructure.word_alignment import (
    AlignmentError,
    alignment_to_word_timings,
)

logger = structlog.get_logger()

TRANSIENT_STATUS_CODES = (429, 500, 502, 503, 504)

class TTSPort(abc.ABC):
    """
    K-501: TTS (Text-to-Speech) Adaptörü Arayüzü
    Ses üretimi ve maliyet takibi için genel sözleşme.
    """
    
    @abc.abstractmethod
    async def generate_audio_stream(self, text: str, output_path: str, voice_id: str) -> None:
        """Metni sese çevirir ve doğrudan diske asenkron yazar."""
        pass
        
    async def generate_audio_with_timing(
        self, text: str, output_path: str, voice_id: str
    ) -> list[WordTiming]:
        """Sesi diske yazar ve sese birebir kelime zamanlamalarını döndürür."""
        raise NotImplementedError(f"{type(self).__name__} kelime zamanlamasını desteklemiyor")

    @abc.abstractmethod
    def get_total_chars_processed(self) -> int:
        """Ledger: Kullanılan toplam karakter bütçesini döndürür."""
        pass


class ElevenLabsAdapter(TTSPort):
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Bellek içi maliyet defteri (Ledger)
        self.total_chars_processed = 0
        self.base_url = "https://api.elevenlabs.io/v1/text-to-speech"
        
    # Sadece HTTP ağ hatalarında (429, 50x) tekrar dener (Tenacity)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    async def generate_audio_stream(self, text: str, output_path: str, voice_id: str) -> None:
        url = f"{self.base_url}/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        
        logger.info("TTS İsteği Başlıyor", karakter_sayisi=len(text), hedef_dosya=output_path)
        
        async with httpx.AsyncClient() as client:
            request = client.build_request("POST", url, json=payload, headers=headers, timeout=60.0)
            response = await client.send(request, stream=True)
            
            # 429 ve 50x hatalarında exception fırlat ki Tenacity tetiklensin
            if response.status_code in (429, 500, 502, 503, 504):
                response.raise_for_status()
            elif response.status_code != 200:
                # 400, 401 gibi kalıcı hatalarda direkt çök (Tekrar denemenin mantığı yok)
                text_error = await response.aread()
                raise ValueError(f"ElevenLabs Kalıcı API Hatası: {response.status_code} - {text_error.decode('utf-8')}")
                
            # --- BELLEK İZOLASYONU (CHUNK STREAMING) ---
            # Ses dosyasını (örneğin 10MB) tek seferde RAM'e yüklemek yasak. 
            # 8KB'lık parçalar (chunk) halinde çekip doğrudan diske basıyoruz.
            async with aiofiles.open(output_path, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    
        # Başarılı ağ isteği sonrası maliyet defterini güncelle
        self.total_chars_processed += len(text)
        logger.info("TTS İsteği Başarılı (Stream to Disk)", toplam_kullanim=self.total_chars_processed)
        
    # Zamanlamalı uç nokta JSON döner (ses base64 içinde); stream edilemez, ses RAM'e alınır.
    # 60 sn'lik bir senaryo ~1 MB olduğundan kabul edilebilir.
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    async def generate_audio_with_timing(
        self, text: str, output_path: str, voice_id: str
    ) -> list[WordTiming]:
        url = f"{self.base_url}/{voice_id}/with-timestamps"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }

        logger.info("TTS (zamanlamalı) isteği başlıyor", karakter_sayisi=len(text), hedef_dosya=output_path)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=120.0)

        if response.status_code in TRANSIENT_STATUS_CODES:
            response.raise_for_status()
        elif response.status_code != 200:
            raise ValueError(f"ElevenLabs Kalıcı API Hatası: {response.status_code} - {response.text}")

        try:
            body = response.json()
            audio = base64.b64decode(body["audio_base64"], validate=True)
        except (json.JSONDecodeError, KeyError, TypeError, binascii.Error) as exc:
            raise ValueError(f"ElevenLabs yanıtı çözümlenemedi: {type(exc).__name__}: {exc}") from exc
        if not audio:
            raise ValueError("ElevenLabs boş ses döndürdü")

        # Hizalama bozuksa dosya hiç yazılmaz (yarım sonuç bırakmamak için)
        try:
            timings = alignment_to_word_timings(body.get("alignment"))
        except AlignmentError:
            logger.error("TTS hizalaması geçersiz", hedef_dosya=output_path)
            raise

        async with aiofiles.open(output_path, 'wb') as f:
            await f.write(audio)

        self.total_chars_processed += len(text)
        logger.info("TTS (zamanlamalı) başarılı", kelime=len(timings), toplam_kullanim=self.total_chars_processed)
        return timings

    def get_total_chars_processed(self) -> int:
        return self.total_chars_processed
