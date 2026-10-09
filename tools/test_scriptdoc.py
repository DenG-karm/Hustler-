import sys
import os
import json
import structlog
from pydantic import ValidationError

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.domain.models.script import ScriptDoc

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M4 K-401: SCRIPTDOC VE JSON SCHEMA TESTİ ---")
    
    # --- 1. TEST: HATALI VERİ (Sınır ihlalleri ve eksik alan) ---
    logger.info(">>> 1. TEST: Kasıtlı Hatalı Veri Gönderimi <<<")
    bad_data = {
        # Hook kasıtlı olarak 150 karakteri geçiyor
        "hook": "Bu kanca cümlesi o kadar uzun ki yüz elli karakter sınırını kesinlikle ama kesinlikle ihlal edecektir. Pydantic'in bu durumu anında tespit edip ValidationError fırlatmasını bekliyoruz. Gördüğün gibi hala yazıyorum ve bitmedi.",
        "body": ["Burası ana metin", "Gelişme kısmı"],
        # cta alanı BİLEREK SİLİNDİ (Eksik Anahtar Hatası)
        "estimated_duration": -5 # gt=0 kuralı ihlali
    }
    
    try:
        doc = ScriptDoc.model_validate(bad_data)
        logger.error("KRİTİK HATA: Pydantic bozuk veriyi kabul etti! Bu olmamalıydı.")
        sys.exit(1)
    except ValidationError as e:
        logger.info("✅ BAŞARILI RED! Pydantic hatalı veriyi acımasızca reddetti.")
        # Kaç farklı hata olduğunu logluyoruz
        logger.info("Hata Detayları", hata_sayisi=e.error_count(), icerik=str(e))
        
    # --- 2. TEST: DOĞRU VERİ ---
    logger.info(">>> 2. TEST: Kurallara Tam Uyan Doğru Veri Gönderimi <<<")
    good_data = {
        "hook": "Sadece 3 adımda finansal özgürlüğün sırrını keşfet!",
        "body": [
            "İlk adımda bütçeni takip etmelisin.", 
            "İkinci adımda harcamalarını kısmalısın.", 
            "Son adımda ise yatırıma yönelmelisin."
        ],
        "cta": "Daha fazlası için profilimdeki linke tıkla!",
        "estimated_duration": 45
    }
    
    try:
        doc = ScriptDoc.model_validate(good_data)
        logger.info("✅ DOĞRULAMA BAŞARILI! Veri başarıyla Python nesnesine dönüştü.", 
                    hook_kisaltmasi=doc.hook[:20]+"...", 
                    sure=doc.estimated_duration)
        
        # LLM'e Dayatılacak Şemayı Ekrana Bas (Kanıt Çıktısı)
        schema_json = ScriptDoc.get_llm_schema()
        logger.info("LLM Adaptörüne Dayatılacak JSON Schema Sözleşmesi:")
        print(json.dumps(schema_json, indent=2, ensure_ascii=False))
        
    except ValidationError as e:
        logger.error("Beklenmeyen Hata: Doğru veri reddedildi!", error=str(e))
        sys.exit(1)
        
    logger.info("--- K-401 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
