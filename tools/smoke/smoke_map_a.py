import sys
import os
import structlog

# Windows Unicode sorunları için stdout UTF-8 zorlaması
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.domain.map_a import analyze_transcript

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M3 K-304: MAP A (Deterministik Filtreleme) TESTİ ---")
    
    # SENARYO 1: Kelime Barajına Takılan (Kısa) veya Çok Yavaş
    text_short = "Merhaba arkadaşlar. Bugün çok güzel." * 4 # Toplam 16 kelime
    duration_short = 60 # 1 Dakika (Çok Yavaş)
    
    # SENARYO 2: Normal Hızda ve CTA içeren (Geçecek)
    text_normal = ("Videoma hoşgeldiniz. Bu içeriği beğendiyseniz kanalıma abone ol demeyi unutmayın. "
                   "Ayrıca tüm detaylar için link bio'da yer alıyor. Şimdi ana konuya geçelim. "
                   "Burada konuşmaya ve kelime sayısını doldurmaya devam ediyorum. ") * 4 # ~100 kelime
    duration_normal = 60 # 1 Dakika (~100 WPM - İdeal)
    
    # SENARYO 3: Çok Hızlı (Makine/Gürültü)
    text_fast = "kelime " * 300 # 300 Kelime
    duration_fast = 60 # 1 Dakikada 300 kelime (Çok Hızlı)
    
    scenarios = [
        {"name": "1. Çok Kısa / Yavaş Video", "text": text_short, "duration": duration_short},
        {"name": "2. Normal ve CTA'lı Video", "text": text_normal, "duration": duration_normal},
        {"name": "3. Aşırı Hızlı Video", "text": text_fast, "duration": duration_fast},
    ]
    
    for s in scenarios:
        res = analyze_transcript(str(s["text"]), int(str(s["duration"])))
        
        if res.is_accepted:
            logger.info("✅ GEÇTİ", 
                senaryo=s["name"], 
                wpm=res.wpm, 
                kelime=res.word_count, 
                cta_var=res.has_cta
            )
        else:
            logger.warning("❌ REDDEDİLDİ", 
                senaryo=s["name"], 
                wpm=res.wpm, 
                kelime=res.word_count, 
                cta_var=res.has_cta,
                sebep=res.rejection_reason
            )

    logger.info("--- K-304 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
