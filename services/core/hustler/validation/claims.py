import json
import structlog
from typing import List, Literal
from pydantic import BaseModel, Field

from services.core.hustler.infrastructure.llm_port import LLMPort

logger = structlog.get_logger()

class ClaimReport(BaseModel):
    """
    K-405: İddia Raporu (Claim Report) Sözleşmesi
    LLM'in yapısal çıktı (Structured Output) olarak dönmek zorunda olduğu veri formatı.
    """
    is_safe: bool = Field(
        ..., 
        description="Metin yasadışı iddialardan, sahte finansal/sağlık vaatlerinden veya toksik içerikten arınmış mı?"
    )
    flagged_claims: List[str] = Field(
        ..., 
        description="Eğer is_safe False ise, tespit edilen şüpheli iddiaların (cümlelerin) tam listesi. Temizse boş liste."
    )
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ..., 
        description="Metnin genel risk seviyesi."
    )

class ScriptStatusDecider:
    """
    Onay Durumu (State Machine) Karar Mekanizması
    Senaryonun M5 (Ses ve Render) hattına geçip geçemeyeceğini kati kurallarla belirler.
    """
    @staticmethod
    def get_final_status(report: ClaimReport) -> str:
        # İhlal içeren veya Yüksek Riskli senaryo ASLA üretime giremez
        if not report.is_safe or report.risk_level == "HIGH":
            return "REJECTED"
        
        # Şüpheli ama kesin tehlike olmayan durumlarda insan onayı beklenir
        if report.risk_level == "MEDIUM":
            return "PENDING_REVIEW"
            
        # Tamamen güvenli
        return "APPROVED"

class ClaimMarker:
    """
    İddia İşaretleyici Sınıf
    Senaryo metnini LLM'e göndererek iddia/kural ihlali taraması yapar.
    """
    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port
        
    async def verify_claims(self, script_text: str) -> ClaimReport:
        schema = ClaimReport.model_json_schema()
        
        prompt = (
            f"Bir içerik denetleyicisisin (Moderator). Aşağıdaki metni finansal vaat, "
            f"dolandırıcılık, sahte sağlık iddiaları veya topluluk kuralları ihlali açısından analiz et.\n\n"
            f"LÜTFEN ÇIKTIYI KESİNLİKLE ŞU JSON ŞEMASINA (Structured Output) UYGUN OLARAK VER:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Sadece saf JSON dön, ekstra açıklama ekleme.\n\n"
            f"METİN:\n{script_text}"
        )
        
        res = await self.llm_port.generate_text(prompt)
        
        # Markdown etiketlerini temizle (Eğer LLM kural dışına çıkıp ```json koyarsa)
        clean_text = res.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        data = json.loads(clean_text.strip())
        
        # Pydantic ile gelen yapıyı doğrula ve dön
        return ClaimReport(**data)
