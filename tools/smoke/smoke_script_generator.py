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

from services.core.hustler.domain.models.template import TemplateSpec, RenderConfig, SafeZone
from services.core.hustler.generators.script_generator import ScriptGenerator, ScriptGenerationError
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse

logger = structlog.get_logger()

class MockLLMPort(LLMPort):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK", max_tokens=9999)
        self.call_count = 0
        
    async def generate_text(self, prompt: str) -> LLMResponse:
        self.call_count += 1
        logger.info(f"🔥 LLM API ÇAĞRISI YAPILDI (Deneme: {self.call_count}) 🔥")
        
        if self.call_count == 1:
            # 1. Deneme: Kasıtlı bozuk JSON (Kural İhlali: CTA eksik, body string verilmiş)
            bad_json = {
                "hook": "Bu kanca fena değil.",
                "body": "Sahneler dizi olmalı ama string verdim. Bu Pydantic'i patlatacak."
            }
            return LLMResponse(json.dumps(bad_json), 10, 10, 20)
        else:
            # 2. Deneme: Kusursuz JSON
            good_json = {
                "hook": "Doğru kanca",
                "body": ["Sahne 1'de bu olacak", "Sahne 2'de şu olacak"],
                "cta": "Kanala abone ol",
                "estimated_duration": 45
            }
            return LLMResponse(json.dumps(good_json), 10, 10, 20)

async def main() -> None:
    logger.info("--- M4 K-403: SENARYO ÜRETİCİ (SCRIPT GENERATOR) TESTİ ---")
    
    # Bağımlılıklar
    llm = MockLLMPort()
    generator = ScriptGenerator(llm_port=llm)
    
    # Template Sözleşmesi
    template = TemplateSpec(
        name="Test Şablonu",
        target_duration_sec=60,
        max_scenes=5,
        allowed_tones=["eğitici"], render_config=RenderConfig(width=1080, height=1920, fps=30, bg_color="#000", safe_zone=SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10))
    )
    context = "Yapay zeka ile nasıl video üretilir?"
    
    try:
        # Üretimi Başlat
        script_doc = await generator.generate_script(template, context)
        
        logger.info("✅ İŞLEM BAŞARILI! Nihai Senaryo Çıktısı Alındı.", 
                    deneme_sayisi=llm.call_count, 
                    hook=script_doc.hook,
                    sahne_sayisi=len(script_doc.body))
        
        # İlk denemede hata alıp Retry mekanizmasıyla ikinciye gittiğini doğrula
        assert llm.call_count == 2, f"Beklenen API çağrısı sayısı 2, ancak {llm.call_count} yapıldı!"
        
    except ScriptGenerationError as e:
        logger.error("HATA: ScriptGenerationError fırlatıldı ama edilmemeliydi!", error=str(e))
        sys.exit(1)
        
    logger.info("✅ Retry (Direnç) Mekanizması hatalı veriyi başarıyla yakalayıp 2. denemede çözdü.")
    logger.info("--- K-403 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
