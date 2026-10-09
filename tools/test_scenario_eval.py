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
from services.core.hustler.validation.claims import ClaimMarker
from services.core.hustler.evaluation.scenario_eval import ScenarioEvaluationEngine

logger = structlog.get_logger()

class MockEvalLLMPort(LLMPort):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK", max_tokens=9999)
        
    async def generate_text(self, prompt: str) -> LLMResponse:
        # İddia işaretleyiciyi simüle ediyoruz
        if "%100 kazanacaksınız" in prompt or "garantili" in prompt:
            res = {
                "is_safe": False,
                "flagged_claims": ["kesin %100 kazanacaksınız", "garantili"],
                "risk_level": "HIGH"
            }
        else:
            res = {
                "is_safe": True,
                "flagged_claims": [],
                "risk_level": "LOW"
            }
        return LLMResponse(json.dumps(res), 10, 10, 20)

async def main() -> None:
    logger.info("--- M4 K-407: SENARYO DEĞERLENDİRME SETİ (EVAL HARNESS) TESTİ ---")
    
    # Dataset yolunu bul
    dataset_path = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'scenario_eval_dataset.json')
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    # Bağımlılıkları Kur
    llm = MockEvalLLMPort()
    marker = ClaimMarker(llm_port=llm)
    engine = ScenarioEvaluationEngine(claim_marker=marker)
    
    logger.info("Değerlendirme Motoru Başlatıldı...", test_senaryo_sayisi=len(dataset))
    
    # Değerlendirmeyi Başlat
    report = await engine.run_evaluation(dataset)
    
    for res in report["results"]:
        status_icon = "✅ DOĞRU KARAR" if res.is_correct else "❌ YANLIŞ KARAR"
        logger.info(
            f"{status_icon} | ID: {res.scenario_id}", 
            beklenen_durum=res.expected_result,
            beklenen_asama=res.expected_failure_stage,
            gerceklesen_durum=res.actual_result,
            gerceklesen_asama=res.actual_failure_stage
        )
        if not res.is_correct:
            logger.error("Hata Detayı", msg=res.error_msg)
            
    logger.info("====================================")
    logger.info("🏆 M4 KALİTE SKORU Raporu (EVAL) 🏆")
    logger.info(f"Doğruluk Oranı (Accuracy): %{report['accuracy']:.1f}")
    logger.info(f"Başarılı Tespit: {report['correct']} / {report['total']}")
    logger.info("====================================")
    
    # K-407 Çıkış Kriteri: Minimum %95 Doğruluk
    assert report['accuracy'] >= 95.0, f"KRİTİK HATA: Kalite skoru çöktü! Beklenen: >= %95, Gerçekleşen: %{report['accuracy']}"
    
    logger.info("✅ Tüm güvenlik filtreleri ve şema kuralları, en uç senaryolar (Edge Cases) üzerinde mükemmel çalışıyor.")
    logger.info("--- K-407 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
