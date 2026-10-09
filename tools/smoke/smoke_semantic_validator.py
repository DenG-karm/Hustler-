import sys
import os
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec, RenderConfig, SafeZone
from services.core.hustler.validation.semantic import SemanticValidator, SemanticValidationError

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M4 K-404: ANLAMSAL DOĞRULAYICI (SEMANTIC VALIDATOR) TESTİ ---")
    
    template = TemplateSpec(
        name="Test", 
        target_duration_sec=30, # Hedef süre 30 saniye
        max_scenes=3, 
        allowed_tones=["ciddi"], render_config=RenderConfig(width=1080, height=1920, fps=30, bg_color="#000", safe_zone=SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10))
    )
    
    # 30 saniyelik bir video için WPM=140 ise ideal kelime sayısı 70'tir.
    # %15 sapma payı ile ~59 ile 80 kelime arasına izin veriyoruz.

    # --- 1. TEST: TEMİZ METİN ---
    logger.info(">>> TEST 1: Kurallara Uyan Temiz Metin (~70 Kelime) <<<")
    # Kelimeleri birbirinden farklı ve yaklaşık 70 kelime olan bir metin hazırlayalım.
    clean_words = (
        "Bu birinci cümle tamamen rastgele olarak yazılıyor ve uzun tutuluyor. "
        "İkinci kısımda tekrara düşmemeye özen gösteriyorum ki sistem hata vermesin. "
        "Üçüncü adım yapay zekanın gelişmiş analitik yeteneklerini anlatır ve detaylandırır. "
        "Dördüncü satır başka bir dünyayı inanılmaz bir görsellikle betimliyor. "
        "Beşinci bölümde işler daha da karmaşıklaşıyor, senaryo çok ilginç bir hal alıyor. "
        "Altıncı cümlenin sonuna doğru toplam kelime sayımız yetmiş hedefine yaklaşıyor. "
        "Kapanışta herkes mutlu mesut bir şekilde videodan harika bir deneyimle ayrılıyor."
    )
    
    script_clean = ScriptDoc(
        hook="Temiz başlangıç kancası", 
        body=[clean_words], 
        cta="Abone olmayı sakın unutma dostum", 
        estimated_duration=30
    )
    
    try:
        SemanticValidator.validate(script_clean, template)
        logger.info("✅ TEST 1 BAŞARILI: Temiz metin sorunsuz geçti.")
    except SemanticValidationError as e:
        logger.error("KRİTİK HATA: Temiz metin reddedildi!", error=str(e))
        sys.exit(1)

    # --- 2. TEST: SÜRE (KELİME) SAPMASI İHLALİ ---
    logger.info(">>> TEST 2: Aşırı Kısa Metin (Süre İhlali) <<<")
    script_short = ScriptDoc(
        hook="Kısa kanca", 
        body=["Sadece birkaç kelime yazdım ve bitti."], 
        cta="Kapanış", 
        estimated_duration=30
    )
    
    try:
        SemanticValidator.validate(script_short, template)
        logger.error("KRİTİK HATA: Aşırı kısa metin kabul edildi!")
        sys.exit(1)
    except SemanticValidationError as e:
        logger.info("✅ TEST 2 BAŞARILI RED: Metin uzunluğu hedefe uymadı.", hata_detayi=str(e))

    # --- 3. TEST: N-GRAM TEKRARI (LLM Halüsinasyonu) ---
    logger.info(">>> TEST 3: Tekrarlayan Bloklar (Halüsinasyon İhlali) <<<")
    # Kelime sayısı 70 olsun diye 14 defa tekrar ediyoruz ama 4 kelimelik "ben iyi bir yapay zekayım" bloğu tekrara giriyor.
    hallucinated = "ben iyi bir yapay zekayım. " * 14 
    script_loop = ScriptDoc(
        hook="Tekrar kancası", 
        body=[hallucinated], 
        cta="Kapanış kısmı", 
        estimated_duration=30
    )
    
    try:
        SemanticValidator.validate(script_loop, template)
        logger.error("KRİTİK HATA: Tekrarlayan (bozuk) metin kabul edildi!")
        sys.exit(1)
    except SemanticValidationError as e:
        logger.info("✅ TEST 3 BAŞARILI RED: LLM tekrarı (N-Gram) anında tespit edildi.", hata_detayi=str(e))
        
    logger.info("--- K-404 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
