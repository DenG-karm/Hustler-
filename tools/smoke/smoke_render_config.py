import sys
import os
import structlog
from pydantic import ValidationError

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.domain.models.template import RenderConfig

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M6 K-601: RENDER CONFIG VE SAFE ZONE TESTİ ---")
    
    # 1. GEÇERLİ KONFİGÜRASYON
    logger.info(">>> TEST 1: Geçerli Konfigürasyon (1080x1920, 30 FPS) <<<")
    valid_data = {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "bg_color": "#000000",
        "safe_zone": {
            "margin_top": 200,
            "margin_bottom": 250,
            "margin_left": 50,
            "margin_right": 50
        }
    }
    
    try:
        cfg = RenderConfig.model_validate(valid_data)
        logger.info("✅ BAŞARILI KABUL! Konfigürasyon Pydantic nesnesine dönüştü.", 
                    width=cfg.width, height=cfg.height, fps=cfg.fps, 
                    safe_zone=cfg.safe_zone.model_dump())
    except ValidationError as e:
        logger.error("HATA: Geçerli konfigürasyon reddedildi!", error=str(e))
        sys.exit(1)
        
    # 2. GEÇERSİZ KONFİGÜRASYON (1920x1080, 60 FPS)
    logger.info(">>> TEST 2: Geçersiz Konfigürasyon (1920x1080, 60 FPS) <<<")
    invalid_data = {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "bg_color": "#000000",
        "safe_zone": {
            "margin_top": 200,
            "margin_bottom": 250,
            "margin_left": 50,
            "margin_right": 50
        }
    }
    
    try:
        cfg = RenderConfig.model_validate(invalid_data)
        logger.error("KRİTİK HATA: Pydantic geçersiz konfigürasyonu kabul etti!")
        sys.exit(1)
    except ValidationError as e:
        logger.info("✅ BAŞARILI RED! Pydantic hatalı değerleri acımasızca reddetti.")
        for err in e.errors():
            logger.info("İhlal Detayı", alan=err["loc"][0], hata_tipi=err["type"], mesaj=err["msg"])
            
    logger.info("--- K-601 TESTİ TAMAMLANDI ---")

if __name__ == '__main__':
    main()
