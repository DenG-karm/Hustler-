import sys
import os
import structlog
from pydantic import ValidationError

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.domain.models.template import TemplateSpec

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M4 K-402: TEMPLATESPEC SÖZLEŞMESİ TESTİ ---")
    
    # --- 1. TEST: HATALI KONFİGÜRASYON ---
    logger.info(">>> 1. TEST: Kuralları İhlal Eden Konfigürasyon <<<")
    bad_config = {
        "name": "Ab",             # HATA: min_length=3 (2 verildi)
        "target_duration_sec": 5, # HATA: ge=15 (5 verildi)
        "max_scenes": 15,         # HATA: le=10 (15 verildi)
        "allowed_tones": [],      # HATA: min_length=1 (Boş liste verildi)
        "render_config": {"width": 1080, "height": 1920, "fps": 30, "bg_color": "#000000", "safe_zone": {"margin_top": 100, "margin_bottom": 100, "margin_left": 50, "margin_right": 50}}
    }
    
    try:
        doc = TemplateSpec.model_validate(bad_config)
        logger.error("KRİTİK HATA: Pydantic bozuk şablonu esnek davranarak kabul etti! Bu olmamalıydı.")
        sys.exit(1)
    except ValidationError as e:
        logger.info("✅ BAŞARILI RED! Pydantic hatalı şablon konfigürasyonunu acımasızca reddetti.")
        logger.info("İhlal Edilen Kural Sayısı", hata_sayisi=e.error_count())
        for err in e.errors():
            logger.info("İhlal Detayı", alan=err["loc"][0], hata_tipi=err["type"], mesaj=err["msg"])
            
    # --- 2. TEST: DOĞRU KONFİGÜRASYON ---
    logger.info(">>> 2. TEST: Kurallara Tam Uyan Konfigürasyon <<<")
    good_config = {
        "name": "Motivasyon Shorts Şablonu",
        "target_duration_sec": 60,
        "max_scenes": 5,
        "allowed_tones": ["ilham verici", "heyecanlı", "didaktik"],
        "render_config": {"width": 1080, "height": 1920, "fps": 30, "bg_color": "#000000", "safe_zone": {"margin_top": 100, "margin_bottom": 100, "margin_left": 50, "margin_right": 50}}
    }
    
    try:
        doc = TemplateSpec.model_validate(good_config)
        logger.info("✅ DOĞRULAMA BAŞARILI! Şablon başarıyla Pydantic nesnesine dönüştü.", 
                    isim=doc.name, 
                    hedef_sure=doc.target_duration_sec, 
                    maks_sahne=doc.max_scenes,
                    tonlar=doc.allowed_tones)
    except ValidationError as e:
        logger.error("Beklenmeyen Hata: Kurallara uyan doğru şablon reddedildi!", error=str(e))
        sys.exit(1)
        
    logger.info("--- K-402 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
