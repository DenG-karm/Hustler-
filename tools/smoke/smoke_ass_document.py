import sys
import os
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming
from services.core.hustler.generators.subtitle_generator import SubtitleStyle, AssDocument

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M5 K-503: ASS DOCUMENT VE SUBTITLE STYLE TESTİ ---")
    
    # Sentetik kelime listesi (K-502'den geçmiş gibi)
    words = [
        WordTiming(word="Merhaba", start_ms=0, end_ms=500),
        WordTiming(word="bu", start_ms=500, end_ms=1900),
        WordTiming(word="bir", start_ms=1900, end_ms=2500),
        WordTiming(word="testtir.", start_ms=2500, end_ms=3141)
    ]
    
    # Katı Tipografik Stiller
    style = SubtitleStyle(
        font_name="Impact",
        font_size=120,
        primary_color="&H00FFFFFF&", # Beyaz
        highlight_color="&H0000FFFF&", # Sarı
        alignment=5, # Merkez
        margin_v=50
    )
    
    # Üretim
    ass_content = AssDocument.generate(words, style)
    
    logger.info(">>> DERLENMİŞ .ASS ÇIKTISI <<<")
    # Terminale asıl string çıktısını basalım
    print("--------------------------------------------------")
    print(ass_content)
    print("--------------------------------------------------")
    
    # --- DOĞRULAMALAR ---
    
    # 1. Başlık ve Format Deklarasyonları
    assert "[Script Info]" in ass_content, "HATA: [Script Info] başlığı eksik!"
    assert "[V4+ Styles]" in ass_content, "HATA: [V4+ Styles] başlığı eksik!"
    assert "[Events]" in ass_content, "HATA: [Events] başlığı eksik!"
    
    # 2. Milisaniye -> ASS Zaman Formatı Çevirisi (0:00:01.90)
    assert "0:00:01.90" in ass_content, "HATA: 1900ms zaman çevirisi hatalı! (0:00:01.90 bekleniyordu)"
    assert "0:00:03.14" in ass_content, "HATA: 3141ms zaman çevirisi hatalı! (0:00:03.14 bekleniyordu)"
    
    # 3. Kelime Vurgusu (Karaoke/Highlight Renk Etiketi)
    assert "{\\c&H0000FFFF&}Merhaba" in ass_content, "HATA: Vurgu (Highlight) etiketi 1. kelimeye uygulanmamış!"
    assert "{\\c&H0000FFFF&}testtir." in ass_content, "HATA: Vurgu (Highlight) etiketi 4. kelimeye uygulanmamış!"
    
    logger.info("✅ ASS Başlıkları ve Format Deklarasyonları katı standartlara tamamen uygun.")
    logger.info("✅ Milisaniye -> H:MM:SS.cs çevirisi (Zaman Formatı) kusursuz çalışıyor.")
    logger.info("✅ Kelime Vurgu (Highlight) renk etiketleri metne başarıyla gömüldü.")
    logger.info("--- K-503 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
