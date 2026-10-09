import sys
import os
import json
import asyncio
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.validation.claims import ClaimMarker, ScriptStatusDecider

logger = structlog.get_logger()

# Test amaçlı Fake LLM adaptörü
class MockLLMPort(LLMPort):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK", max_tokens=9999)
        
    async def generate_text(self, prompt: str) -> LLMResponse:
        # Prompt içinde toksik metnimiz geçiyorsa Yüksek Risk (HIGH) dön
        if "%100 kazanacaksınız" in prompt:
            res = {
                "is_safe": False,
                "flagged_claims": ["kesin %100 kazanacaksınız", "hiçbir riski yok hemen yatırım yapın"],
                "risk_level": "HIGH"
            }
        else:
            # Temiz bir metinse
            res = {
                "is_safe": True,
                "flagged_claims": [],
                "risk_level": "LOW"
            }
        return LLMResponse(json.dumps(res), 10, 10, 20)

async def main() -> None:
    logger.info("--- M4 K-405: İDDİA İŞARETLEYİCİ (CLAIM MARKER) TESTİ ---")
    
    llm = MockLLMPort()
    marker = ClaimMarker(llm_port=llm)
    
    clean_text = "Bugün doğada çok güzel bir yürüyüş yaptık. Ormanın havası harikaydı, kuşların sesi ruhumuzu dinlendirdi."
    toxic_text = "Bu yöntemle kesin %100 kazanacaksınız, hiçbir riski yok hemen yatırım yapın ve zengin olun! Fırsatı kaçırma."
    
    # --- 1. TEST: TEMİZ METİN ---
    logger.info(">>> TEST 1: Temiz Metin (Bilgi / Hikaye) <<<")
    report1 = await marker.verify_claims(clean_text)
    status1 = ScriptStatusDecider.get_final_status(report1)
    
    logger.info("Temiz Metin Sonucu", 
                is_safe=report1.is_safe, 
                risk=report1.risk_level, 
                sonuc_durumu=status1)
                
    assert status1 == "APPROVED", "Temiz metin yanlışlıkla engellendi!"
    
    # --- 2. TEST: TOKSİK METİN ---
    logger.info(">>> TEST 2: Finansal Vaat / Toksik İhlal <<<")
    report2 = await marker.verify_claims(toxic_text)
    status2 = ScriptStatusDecider.get_final_status(report2)
    
    logger.info("Toksik Metin Sonucu", 
                is_safe=report2.is_safe, 
                risk=report2.risk_level, 
                yakalanan_iddialar=report2.flagged_claims,
                sonuc_durumu=status2)
                
    assert status2 == "REJECTED", "Toksik metin engellenmedi ve Render hattına sızdı!"
    
    logger.info("✅ İddia İşaretleyici, toksik metni ve sahte vaatleri anında yakalayıp (REJECTED) üretim hattını kapattı.")
    logger.info("--- K-405 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
