from pydantic import BaseModel, Field
from typing import Any, List

class ScriptDoc(BaseModel):
    """
    K-401: Senaryo Şeması (JSON Schema Sözleşmesi)
    LLM'in halüsinasyon görmesini (gevşek Any veya standard dict kullanımını) engelleyen,
    katı uzunluk ve tip doğrulamalarıyla donatılmış veri modeli.
    """
    hook: str = Field(
        ..., 
        max_length=150, 
        description="Videonun ilk 3 saniyesinde izleyiciyi yakalayacak kanca cümlesi."
    )
    body: List[str] = Field(
        ..., 
        min_length=1, 
        description="Ana senaryo metni. Her bir öğe bir sahneyi veya cümleyi temsil eder."
    )
    cta: str = Field(
        ..., 
        max_length=100, 
        description="Videonun sonundaki eylem çağrısı (Call to Action)."
    )
    estimated_duration: int = Field(
        ..., 
        gt=0, 
        description="Senaryonun tahmin edilen süresi (saniye cinsinden)."
    )
    
    @classmethod
    def get_llm_schema(cls) -> dict[str, Any]:
        """LLM adaptörüne (Gemini/OpenAI) Structured Output olarak verilecek şemayı üretir."""
        return cls.model_json_schema()
