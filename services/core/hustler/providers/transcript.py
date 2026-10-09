import asyncio
from dataclasses import dataclass
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import TranscriptsDisabled, VideoUnavailable

@dataclass
class TranscriptResult:
    video_id: str
    text: Optional[str] = None
    language_code: Optional[str] = None
    translation_required: bool = False
    requires_whisper: bool = False
    error_message: Optional[str] = None

class TranscriptProvider:
    """
    K-302: Priority Routing Destekli Altyazı Sağlayıcısı.
    Öncelik 1: YouTube Yerleşik Altyazısı (Hızlı & Ücretsiz)
    Öncelik 2: Whisper Devri (Yavaş & Pahalı)
    """
    def __init__(self, target_language: str = "en"):
        self.target_language = target_language

    def _fetch_native_transcript_sync(self, video_id: str) -> TranscriptResult:
        try:
            # Sınıfı örneklendir ve list metodunu çağır
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            # Manuel altyazıyı önceliklendirerek ilk bulduğumuz altyazıyı alıyoruz
            transcript = None
            for t in transcript_list:
                if not t.is_generated:
                    transcript = t
                    break
                    
            if not transcript:
                # Manuel yoksa otomatik olana düş
                for t in transcript_list:
                    if t.is_generated:
                        transcript = t
                        break
                        
            if not transcript:
                # Hiçbir dilde altyazı yok
                return TranscriptResult(video_id=video_id, requires_whisper=True, error_message="No transcripts found")
            
            # Altyazı bulundu! Hedef dili kontrol et.
            lang_code = transcript.language_code
            translation_required = not lang_code.startswith(self.target_language)
            
            # Veriyi çek ve metni birleştir
            transcript_data = transcript.fetch()
            full_text = " ".join([item.text for item in transcript_data])
            
            return TranscriptResult(
                video_id=video_id,
                text=full_text,
                language_code=lang_code,
                translation_required=translation_required,
                requires_whisper=False
            )
            
        except (TranscriptsDisabled, VideoUnavailable) as e:
            # Video kapalıysa veya altyazılar bilerek kapatılmışsa sessizce Whisper'a devret
            return TranscriptResult(video_id=video_id, requires_whisper=True, error_message=type(e).__name__)
        except Exception as e:
            # Ağıl / Beklenmeyen hatalar da ana akışı bozmamalı
            return TranscriptResult(video_id=video_id, requires_whisper=True, error_message=f"Unknown Error: {str(e)}")

    async def get_transcript(self, video_id: str) -> TranscriptResult:
        """
        Asenkron İstek Yönlendirici.
        youtube_transcript_api blocking (requests tabanlı) olduğu için, 
        event-loop'u kitlememesi adına thread-pool (executor) kullanılarak çalıştırılır.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_native_transcript_sync, video_id)
