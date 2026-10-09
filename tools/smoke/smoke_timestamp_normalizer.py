import sys
import os
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.timestamp_normalizer import TimestampNormalizer

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M5 K-502: ZAMAN DAMGASI NORMALLEŞTİRİCİ TESTİ ---")
    
    # 1. Küsüratlı (float) saniye değerleri
    # 2. 'bu' (bitiş: 2.0s) ve 'bir' (başlangıç: 1.9s) arasında BİLİNÇLİ ÇAKIŞMA var.
    raw_words = [
        {"word": "Merhaba", "start": 0.123, "end": 0.845},
        {"word": "bu",      "start": 1.050, "end": 2.000},   # Bitiş: 2000 ms
        {"word": "bir",     "start": 1.900, "end": 2.500},   # Başlangıç: 1900 ms (ÇAKIŞMA)
        {"word": "testtir.", "start": 2.510, "end": 3.14159}
    ]
    
    logger.info(">>> GİRDİ: Ham (Raw) Zamanlamalar (Saniye Cinsinden) <<<")
    for rw in raw_words:
        logger.info("Ham Veri", kelime=rw["word"], start_sec=rw["start"], end_sec=rw["end"])
    
    # İşlem (Pure Function, Ağa çıkmaz)
    normalized = TimestampNormalizer.normalize_timings(raw_words)
    
    logger.info(">>> ÇIKTI: Normalleştirilmiş Zamanlamalar (Milisaniye Cinsinden) <<<")
    for w in normalized:
        logger.info("Normalleştirilmiş Kelime", word=w.word, start_ms=w.start_ms, end_ms=w.end_ms)
        
    # --- KATK DOĞRULAMALAR ---
    
    # 1. Float Saniyelerin Tam Sayı Milisaniyeye Dönüşümü (1. Kelime)
    assert normalized[0].start_ms == 123, f"HATA: 0.123 sn, 123 ms'ye çevrilemedi! ({normalized[0].start_ms})"
    assert normalized[0].end_ms == 845, f"HATA: 0.845 sn, 845 ms'ye çevrilemedi! ({normalized[0].end_ms})"
    
    # 2. Çakışma Önleme (Overlap Resolution - 2. ve 3. Kelime)
    # Beklenti: 'bu' kelimesi 2000 ms'de bitiyordu, ancak 'bir' 1900 ms'de başladığı için, 
    # 'bu' kelimesinin bitişi acımasızca 1900 ms'ye kırpılmalı.
    assert normalized[1].end_ms == 1900, f"KRİTİK HATA: Çakışma ezilmedi! 2. Kelimenin bitişi hala {normalized[1].end_ms} ms."
    assert normalized[2].start_ms == 1900, "HATA: 3. Kelimenin başlangıcı bozuldu!"
    
    logger.info("✅ Başarılı: Float saniyeler, pürüzsüz Integer milisaniyelere çevrildi.")
    logger.info("✅ Başarılı: Kelimeler arası süre çakışmaları (Overlap) anında ezilerek Altyazı senkron hataları önlendi.")
    logger.info("--- K-502 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
