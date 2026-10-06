import json
import structlog
from typing import Dict, Any, Tuple

from services.core.hustler.infrastructure.llm_port import LLMPort

logger = structlog.get_logger()

class EvalHarness:
    """
    K-309: Prompt Değerlendirme Takımı (Eval Harness)
    Sistem promptundaki küçük bir değişikliğin, analiz kalitesini (başarı oranını)
    düşürüp düşürmediğini matematiksel olarak kanıtlayan test motoru.
    """
    def __init__(self, dataset_path: str, llm_port: LLMPort):
        self.dataset_path = dataset_path
        self.llm_port = llm_port
        with open(dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)

    def _compare(self, ideal: Dict[str, Any], actual: Dict[str, Any]) -> float:
        """
        Ground truth (ideal) ile LLM sonucunu yapısal ve anlamsal olarak kıyaslayıp
        0 ile 100 arası bir Başarı (Accuracy) puanı üretir.
        """
        if not isinstance(actual, dict):
            return 0.0
            
        score = 0.0
        keys_to_check = ["has_hook", "hook_text", "topic"]
        weight = 100.0 / len(keys_to_check)
        
        for k in keys_to_check:
            # Eksik anahtar cezası
            if k not in actual:
                continue
                
            ideal_val = ideal.get(k)
            actual_val = actual.get(k)
            
            # Tip Uyuşmazlığı Cezası (Boolean yerine string "True" döndürmek vs.)
            if type(ideal_val) != type(actual_val):
                continue
                
            if isinstance(ideal_val, bool):
                # Mantıksal Birebir Eşleşme
                if ideal_val == actual_val:
                    score += weight
            elif isinstance(ideal_val, str):
                # Anlamsal kapsama eşleşmesi (Birebir değil, kelime içermesi yeterli)
                # LLM büyük harf veya noktalama kullanmış olabilir
                if ideal_val == "" and actual_val == "":
                    score += weight
                elif ideal_val != "" and actual_val != "":
                    # "linke tıklayın" -> "Linke tıklayın"
                    if ideal_val.lower() in actual_val.lower() or actual_val.lower() in ideal_val.lower():
                        score += weight
                    elif len(ideal_val) > 3 and ideal_val[:4].lower() in actual_val.lower():
                        # Kısmi anlamsal tolerans (Örn: "abone olmayı unutmayın" vs "abone ol")
                        score += weight * 0.8
                        
        return round(score, 2)

    async def evaluate_prompt(self, prompt_template: str) -> float:
        """
        Veri setindeki tüm transkriptleri LLM'den geçirir.
        Geri dönen JSON'ı analiz eder ve Ortalama Başarı Puanını döner.
        """
        total_score = 0.0
        
        for item in self.dataset:
            transcript = item["transcript"]
            ideal = item["ideal_output"]
            
            # Prompt enjeksiyonu
            prompt = prompt_template.replace("{{TRANSCRIPT}}", transcript)
            
            res = await self.llm_port.generate_text(prompt)
            
            try:
                actual = json.loads(res.text)
            except Exception:
                # LLM JSON yerine düz metin döndüyse 0 puan (Hallucination / Bad Format)
                actual = {}
                
            total_score += self._compare(ideal, actual)
            
        avg_score = total_score / len(self.dataset)
        return round(avg_score, 2)

    async def run_regression_test(self, prompt_v1: str, prompt_v2: str) -> Tuple[float, float, float]:
        """Eski ve yeni sürüm promptlarını çarpıştırıp Delta raporu sunar."""
        logger.info("eval_started", version="V1", msg="Optimize edilmiş prompt test ediliyor...")
        score_v1 = await self.evaluate_prompt(prompt_v1)
        
        logger.info("eval_started", version="V2", msg="Bozulmuş prompt test ediliyor...")
        score_v2 = await self.evaluate_prompt(prompt_v2)
        
        delta = round(score_v2 - score_v1, 2)
        
        logger.info("eval_completed", 
            score_v1=score_v1, 
            score_v2=score_v2, 
            delta=delta,
            msg="Gerileme (Regression) tespiti tamamlandı."
        )
        
        return score_v1, score_v2, delta
