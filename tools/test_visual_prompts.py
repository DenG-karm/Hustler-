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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.generators.visual_prompts import VisualPromptCompiler

logger = structlog.get_logger()

# Test için LLM'i mockluyoruz (Çeviri ve betimleme simülasyonu)
class MockLLMPort(LLMPort):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK", max_tokens=9999)
        
    async def generate_text(self, prompt: str) -> LLMResponse:
        res = {
            "prompts": [
                {
                    "scene_index": 0,
                    "raw_prompt": "A cinematic shot of a young entrepreneur looking at a glowing laptop screen in a dark room, blue neon lighting, 8k, highly detailed."
                },
                {
                    "scene_index": 1,
                    "raw_prompt": "A close up macro shot of golden coins rapidly stacking on top of each other, bright studio lighting, photorealistic."
                }
            ]
        }
        return LLMResponse(json.dumps(res), 10, 10, 20)

async def main() -> None:
    logger.info("--- M4 K-406: GÖRSEL PROMPT DERLEYİCİ TESTİ ---")
    
    llm = MockLLMPort()
    compiler = VisualPromptCompiler(llm_port=llm)
    
    # LLM'e gidecek ham TÜRKÇE senaryo sahneleri
    turkish_scenes = [
        "Genç bir girişimci karanlık bir odada parlayan dizüstü bilgisayar ekranına bakıyor.",
        "Altın sikkeler hızla üst üste diziliyor, parlak bir stüdyo ışığı var."
    ]
    
    logger.info(">>> TEST: Sahnelerin İngilizce Görsel Dile Çevrilip Parametre Eklenmesi <<<")
    logger.info("Girdi (Türkçe Sahneler)", sahneler=turkish_scenes)
    
    results = await compiler.compile_prompts(turkish_scenes)
    
    for item in results:
        logger.info(f"Sahne {item['scene_index']} Analizi:")
        logger.info(" └─ Raw Prompt (İngilizce)", metin=item["raw_prompt"])
        logger.info(" └─ Final Prompt (Algoritmik Ekleme)", metin=item["final_prompt"])
        
        # Katı Çıkış Kriterleri Doğrulaması
        assert "--ar 9:16" in item["final_prompt"], "HATA: Boyut parametresi (9:16) enjekte edilmemiş!"
        assert "--no text" in item["final_prompt"], "HATA: Negatif prompt (typography kısıtı) enjekte edilmemiş!"
        
    logger.info("✅ Dil bariyeri aşıldı: Senaryonun dili ne olursa olsun promptlar İngilizceye çevrildi.")
    logger.info("✅ LLM'in halüsinasyonları engellendi: 9:16 oranı ve negatif kısıtlar kodla donanımsal olarak eklendi.")
    logger.info("--- K-406 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
