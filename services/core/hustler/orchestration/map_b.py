import asyncio
import structlog
from typing import List, Dict, Any, Optional

from services.core.hustler.infrastructure.llm_port import LLMPort
from services.core.hustler.infrastructure.inference import InferencePort

logger = structlog.get_logger()

class MapBExecutor:
    """
    K-307: Map B Çalıştırıcısı (Executor)
    Videoları (Transkriptleri) LLM veya Yerel Model üzerinden geçirerek kanca (hook) analizi yapar.
    """
    def __init__(self, llm_port: Optional[LLMPort] = None, inference_port: Optional[InferencePort] = None):
        self.llm_port = llm_port
        self.inference_port = inference_port
        
        # API modu eşzamanlılığı (Dinamik)
        # Ağır I/O, donanım (CPU) kısıtlaması olmadığı için Semaphore(5) ile paralelleştirildi.
        self.api_semaphore = asyncio.Semaphore(5)

    async def _process_single(self, video_id: str, transcript: str, use_local_model: bool = False) -> Dict[str, Any]:
        """Tek bir videonun Map B (LLM/Yerel) analizini yapar."""
        
        # Test amaçlı kasıtlı hata fırlatma (Kısmi Başarısızlık İzolasyonunu doğrulamak için)
        if video_id == "FAIL_ME":
            raise ValueError("Bilinçli Kısmi Başarısızlık Testi (Simülasyon)")
            
        if use_local_model:
            # YEREL MODEL MODU: CpuBudget (Semaphore 1) devreye girer
            if not self.inference_port:
                raise RuntimeError("Yerel model modu seçildi fakat InferencePort yapılandırılmadı!")
            
            # InferencePort içerisindeki cpu_semaphore bizi GPU/CPU kilitlenmesinden korur.
            result = await self.inference_port.run_inference(transcript)
            return {"video_id": video_id, "result": result, "mode": "local_inference"}
        else:
            # API MODU: Ağ eşzamanlılık sınırı (Semaphore 5) devreye girer
            if not self.llm_port:
                raise RuntimeError("API modu seçildi fakat LLMPort yapılandırılmadı!")
            
            async with self.api_semaphore:
                # LLMPort içerisindeki Tenacity (Rate-Limit Backoff) ve Bütçe (Fail-fast) bizi korur
                res = await self.llm_port.generate_text(f"Bu metinden kancayı çıkar: {transcript}")
                return {"video_id": video_id, "result": res.text, "mode": "api_llm"}

    async def execute_batch(self, videos: List[Dict[str, str]], use_local_model: bool = False) -> List[Dict[str, Any]]:
        """
        Gelen video listesini batch halinde işler.
        return_exceptions=True sayesinde Kısmi Başarısızlık İzolasyonu (Partial Failure Isolation) sağlar.
        """
        tasks = []
        for v in videos:
            tasks.append(self._process_single(v["video_id"], v["transcript"], use_local_model))
            
        # Asla çökmez, hatalar da listenin içine Exception objesi olarak düşer
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_output = []
        for v, result in zip(videos, results):
            if isinstance(result, Exception):
                logger.error("map_b_partial_failure", video_id=v["video_id"], error=str(result))
                final_output.append({
                    "video_id": v["video_id"], 
                    "error": str(result), 
                    "status": "FAILED"
                })
            else:
                result["status"] = "SUCCESS"
                final_output.append(result)
                
        return final_output
