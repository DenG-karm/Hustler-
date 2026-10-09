import structlog
from typing import List, Dict, Any
from pydantic import BaseModel, Field

logger = structlog.get_logger()

class WordTiming(BaseModel):
    """
    Milisaniye bazında, örtüşmeyen katı kelime zamanlaması modeli.
    ASS altyazılarında hata/kayma yaratmamak için float değer almaz.
    """
    word: str = Field(..., description="Zamanlanmış metin/kelime.")
    start_ms: int = Field(..., description="Kelimenin başlangıç zamanı (Milisaniye cinsinden tamsayı).")
    end_ms: int = Field(..., description="Kelimenin bitiş zamanı (Milisaniye cinsinden tamsayı).")

class TimestampNormalizer:
    """
    K-502: Zaman Damgası Normalleştirici (Timestamp Normalizer)
    Altyazı ve ses hizalamalarındaki milisaniye kaymalarını ve 
    örtüşen zamanları (overlap) düzelten saf (pure) fonksiyondur.
    Ağ veya I/O kullanmaz.
    """
    @staticmethod
    def normalize_timings(raw_words: List[Dict[str, Any]]) -> List[WordTiming]:
        """
        Ham TTS veya transkript API'lerinden gelen saniye (float) cinsindeki
        verileri tamsayı milisaniyeye (integer) çevirir ve zaman tünelindeki 
        çakışmaları (overlap) kırparak ezer.
        """
        if not raw_words:
            return []
            
        timings = []
        for rw in raw_words:
            word = rw.get("word", "").strip()
            
            # Güvenli Float -> Int Milliseconds dönüşümü
            start_sec = float(rw.get("start", 0))
            end_sec = float(rw.get("end", 0))
            
            start_ms = int(start_sec * 1000)
            end_ms = int(end_sec * 1000)
            
            # Zamanın geriye akmasını (hatalı çıktıları) engelle
            if start_ms > end_ms:
                end_ms = start_ms
                
            timings.append(WordTiming(word=word, start_ms=start_ms, end_ms=end_ms))
            
        # Çakışma Önleme (Overlap Resolution)
        # Bir kelime bitmeden diğeri başlıyorsa, önceki kelimenin süresini kırp.
        for i in range(len(timings) - 1):
            current_word = timings[i]
            next_word = timings[i+1]
            
            if current_word.end_ms > next_word.start_ms:
                logger.debug(
                    "Çakışma (Overlap) Kırpıldı", 
                    w1=current_word.word, 
                    w2=next_word.word, 
                    kesilen_ms=current_word.end_ms - next_word.start_ms
                )
                current_word.end_ms = next_word.start_ms
                
        return timings
