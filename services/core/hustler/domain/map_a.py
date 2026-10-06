import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class MapAResult:
    word_count: int
    wpm: int
    has_cta: bool
    is_accepted: bool
    rejection_reason: Optional[str] = None

# CTA kalıpları (Regex tabanlı)
# Çoğunlukla YouTube ve TikTok ağızlarına (Jargon) uygun kancalar
CTA_PATTERN = re.compile(
    r'\b(abone ol|takip et|beğen|link bio|biyografi|açıklamadaki link|subscribe|follow|like and subscribe|link in bio)\b', 
    re.IGNORECASE
)

# Kesin (Hard) Sınırlar
MIN_WORD_COUNT = 50   # 50 kelimeden az ise konuşma yoktur veya sadece müzik vardır
MIN_WPM = 80          # 80 WPM altı ölü/sıkıcı konuşma kabul edilir
MAX_WPM = 250         # 250 WPM üstü anlaşılamayacak düzeyde makine hızı veya gürültü

def analyze_transcript(text: str, duration_seconds: int) -> MapAResult:
    """
    Saf (Pure) Fonksiyon. 
    Dış bağımlılığı (veritabanı, ağ) yoktur.
    """
    if not text or duration_seconds <= 0:
        return MapAResult(0, 0, False, False, "Boş metin veya geçersiz süre")

    # Kelime sayısı
    words = text.split()
    word_count = len(words)
    
    # WPM (Words Per Minute) Hesaplama
    duration_minutes = duration_seconds / 60.0
    wpm = int(word_count / duration_minutes) if duration_minutes > 0 else 0
    
    # CTA kontrolü
    has_cta = bool(CTA_PATTERN.search(text))
    
    # Filtreleme/Eleme Mantığı
    if word_count < MIN_WORD_COUNT:
        return MapAResult(word_count, wpm, has_cta, False, f"Kelime sayısı yetersiz ({word_count} < {MIN_WORD_COUNT})")
        
    if wpm < MIN_WPM:
        return MapAResult(word_count, wpm, has_cta, False, f"Konuşma hızı çok düşük ({wpm} WPM < {MIN_WPM} WPM)")
        
    if wpm > MAX_WPM:
        return MapAResult(word_count, wpm, has_cta, False, f"Konuşma hızı çok yüksek ({wpm} WPM > {MAX_WPM} WPM)")

    # Testi başarıyla geçen kaliteli veri
    return MapAResult(word_count, wpm, has_cta, True)
