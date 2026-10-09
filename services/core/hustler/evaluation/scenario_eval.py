import structlog
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from dataclasses import dataclass

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec, RenderConfig, SafeZone
from services.core.hustler.validation.semantic import SemanticValidator, SemanticValidationError
from services.core.hustler.validation.claims import ClaimMarker, ScriptStatusDecider

logger = structlog.get_logger()

class _StageFailed(Exception):
    """Bir değerlendirme aşaması reddetti (sonuç zaten kaydedildi)."""


@dataclass
class EvalResult:
    scenario_id: str
    passed: bool
    actual_result: str
    actual_failure_stage: Optional[str]
    expected_result: str
    expected_failure_stage: Optional[str]
    is_correct: bool
    error_msg: str = ""

class ScenarioEvaluationEngine:
    """
    K-407: Senaryo Değerlendirme Motoru (Eval Harness)
    Senaryo veri setini baştan sona (Şema -> Anlamsal -> İddia) 
    filtrelerinden geçirir ve doğruluk skoru (Accuracy) çıkarır.
    """
    def __init__(self, claim_marker: ClaimMarker):
        self.claim_marker = claim_marker
        self.template = TemplateSpec(
            name="Eval Şablonu", 
            target_duration_sec=30, 
            max_scenes=10, 
            allowed_tones=["ciddi"], render_config=RenderConfig(width=1080, height=1920, fps=30, bg_color="#000", safe_zone=SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10))
        )

    async def evaluate_single(self, test_case: Dict[str, Any]) -> EvalResult:
        sid = test_case["id"]
        expected_res = test_case["expected_result"]
        expected_stage = test_case["expected_failure_stage"]
        raw_data = test_case["raw_data"]
        
        actual_res = "PASS"
        actual_stage = None
        err_msg = ""
        
        try:
            # 1. Aşama: K-401 Pydantic Validation (Şema İhlalleri)
            try:
                doc = ScriptDoc(**raw_data)
            except ValidationError as e:
                actual_res = "FAIL"
                actual_stage = "K-401_PYDANTIC"
                err_msg = str(e)
                raise _StageFailed
                
            # 2. Aşama: K-404 Semantic Validation (Süre & N-Gram)
            try:
                SemanticValidator.validate(doc, self.template)
            except SemanticValidationError as e:
                actual_res = "FAIL"
                actual_stage = "K-404_SEMANTIC"
                err_msg = str(e)
                raise _StageFailed
                
            # 3. Aşama: K-405 Claim Marker (Toksik ve Yasadışı İddialar)
            script_text = doc.hook + " " + " ".join(doc.body) + " " + doc.cta
            report = await self.claim_marker.verify_claims(script_text)
            status = ScriptStatusDecider.get_final_status(report)
            
            if status != "APPROVED":
                actual_res = "FAIL"
                actual_stage = "K-405_CLAIM"
                err_msg = f"Rejected with risk: {report.risk_level}"
                raise _StageFailed
                
        except _StageFailed:
            pass  # Hata zaten actual_stage ve actual_res değişkenlerine kaydedildi
        except Exception as e:  # noqa: BLE001 - beklenmeyen hata (örn. bozuk LLM JSON) asla PASS sayılmamalı
            actual_res = "FAIL"
            actual_stage = "ENGINE_ERROR"
            err_msg = f"{type(e).__name__}: {e}"
            
        # Ground Truth Karşılaştırması
        is_correct = (actual_res == expected_res) and (actual_stage == expected_stage)
        
        return EvalResult(
            scenario_id=sid,
            passed=is_correct,
            actual_result=actual_res,
            actual_failure_stage=actual_stage,
            expected_result=expected_res,
            expected_failure_stage=expected_stage,
            is_correct=is_correct,
            error_msg=err_msg
        )

    async def run_evaluation(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tüm testleri sırayla koşup doğruluk oranını (Accuracy) hesaplar."""
        results = []
        correct_count = 0
        total = len(dataset)
        
        for case in dataset:
            res = await self.evaluate_single(case)
            results.append(res)
            if res.is_correct:
                correct_count += 1
                
        accuracy = (correct_count / total) * 100 if total > 0 else 0
        
        return {
            "accuracy": accuracy,
            "total": total,
            "correct": correct_count,
            "results": results
        }
