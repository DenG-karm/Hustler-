import sys
import os
import asyncio
import json
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.evaluation.harness import EvalHarness

logger = structlog.get_logger()

# Test esnasında prompt kalitesine göre fake sonuç üreten Mock LLM
async def mock_execute(prompt: str) -> LLMResponse:
    # prompt içinde [V1] veya [V2] işareti var. Buna göre kaliteyi bozacağız.
    is_v1 = "[V1]" in prompt
    
    # Basit bir kelime taramasıyla hangi transkriptte olduğumuzu anlıyoruz
    if "zengin" in prompt:
        if is_v1:
            res = {"has_hook": True, "hook_text": "linke tıklayın", "topic": "para kazanma"}
        else: # V2 (Bozuk prompt JSON sınırlarını zorluyor, yanlış data veriyor)
            res = {"has_hook": "evet", "hook_text": "zengin olmak", "topic": "bilmiyorum"}
            
    elif "Ormanda" in prompt:
        if is_v1:
            res = {"has_hook": False, "hook_text": "", "topic": "doğa"}
        else:
            return LLMResponse("Burası orman çok güzel bir yer", 5, 5, 10) # Format bozuk (JSON değil)
            
    elif "kaydet" in prompt:
        if is_v1:
            res = {"has_hook": True, "hook_text": "videoyu kaydet", "topic": "yazılım"}
        else:
            res = {"has_hook": False, "topic": "yazılım"} # Eksik anahtar
    else:
        # Diğerleri için default iyi dönüş (V1) ve kötü dönüş (V2)
        if is_v1:
            res = {"has_hook": True, "hook_text": "abone ol", "topic": "genel"}
        else:
            res = {"icerik": "yanlış şema"} # Şema tamamen yanlış
            
    return LLMResponse(json.dumps(res), 10, 10, 20)

async def main() -> None:
    logger.info("--- M3 K-309: PROMPT DEĞERLENDİRME TAKIMI (EVAL HARNESS) TESTİ ---")
    
    llm_port = LLMPort(api_key="MOCK", max_tokens=99999)
    setattr(llm_port, "_execute_network_request", mock_execute)
    
    dataset_path = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'eval_dataset.json')
    harness = EvalHarness(dataset_path, llm_port)
    
    # V1 (İyi Optimize Edilmiş, Sıkı Kuralları olan JSON Prompt)
    prompt_v1 = "[V1] Sen bir analistsin. Sadece JSON formatında dön. Transkript: {{TRANSCRIPT}}"
    
    # V2 (Bozuk, kuralları eksik, serbest bırakan Prompt)
    prompt_v2 = "[V2] Hadi bu metni analiz et, bana ne olduğunu söyle: {{TRANSCRIPT}}"
    
    # Regresyon Testini Başlat
    v1_score, v2_score, delta = await harness.run_regression_test(prompt_v1, prompt_v2)
    
    logger.info("=== DELTA RAPORU ===")
    logger.info(f"V1 Skor (Optimize): {v1_score}")
    logger.info(f"V2 Skor (Bozuk)   : {v2_score}")
    logger.info(f"Gerileme (Delta)  : {delta}")
    
    # Çıkış Kriterleri Doğrulaması (Mock verilerle V1 skoru ~46 çıkmaktadır)
    assert v1_score > 40, f"V1 skoru beklenenden düşük: {v1_score}"
    assert delta < -20, f"Regresyon yakalanamadı! Beklenen düşüş çok daha fazlaydı, Delta: {delta}"
    
    logger.info("✅ Eval Harness, bozulan prompt'un kalitedeki düşüşünü anında matematiksel olarak ispatladı!")
    logger.info("--- K-309 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
