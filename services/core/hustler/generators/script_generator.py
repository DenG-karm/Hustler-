import json
import structlog
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from pydantic import ValidationError

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.infrastructure.llm_port import LLMPort
from services.core.hustler.validation.semantic import SemanticValidator

logger = structlog.get_logger()

class ScriptGenerationError(Exception):
    """Senaryo üretimi tüm denemelere rağmen başarısız olduğunda fırlatılır."""
    pass

class ScriptGenerator:
    """
    K-403: Senaryo Üretici (Script Generator)
    LLM'i kullanarak kısıtlı şablonlara (TemplateSpec) uygun
    katı JSON nesneleri (ScriptDoc) üretir.
    Hatalı üretim durumunda direnç (Retry) mekanizmasına sahiptir.
    """
    def __init__(self, llm_port: LLMPort):
        self.llm_port = llm_port

    # 1. Deneme + 2 Hata Tekrarı = Toplam 3 hak. Sadece JSON veya Pydantic hatalarında tekrarlar.
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((ValidationError, json.JSONDecodeError)),
        reraise=True
    )
    async def _attempt_generation(self, prompt: str) -> ScriptDoc:
        """Gerçek üretim mantığı. Hata alırsa Tenacity tarafından otomatik tekrar denenir."""
        # Şemayı (Structured Output) LLM'e dayatıyoruz
        schema = ScriptDoc.get_llm_schema()
        
        full_prompt = (
            f"{prompt}\n\n"
            f"LÜTFEN ÇIKTIYI KESİNLİKLE AŞAĞIDAKİ JSON ŞEMASINA UYGUN OLARAK VER:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n"
            f"Sadece saf JSON çıktısı üret, hiçbir açıklama veya markdown ekleme."
        )
        
        # LLM'den ham metin iste
        res = await self.llm_port.generate_text(full_prompt)
        
        try:
            # 1. Aşama: Ham metni JSON olarak parse et
            # LLM markdown içinde dönmüşse temizle (```json ... ```)
            clean_text = res.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            raw_dict = json.loads(clean_text)
            
            # 2. Aşama: JSON'ı Pydantic kurallarından geçir
            doc = ScriptDoc(**raw_dict)
            return doc
            
        except json.JSONDecodeError as e:
            logger.warning("script_gen_json_error", error=str(e), msg="LLM bozuk JSON döndü. Tekrar deneniyor...")
            raise
        except ValidationError as e:
            logger.warning("script_gen_validation_error", error_count=e.error_count(), msg="LLM JSON döndü ama kuralları ihlal etti. Tekrar deneniyor...")
            raise

    async def generate_script(self, template: TemplateSpec, context: str) -> ScriptDoc:
        """Senaryo üretimi dışa açık API'si. Maksimum limit aşılırsa çökme yerine ScriptGenerationError fırlatır."""
        target_words = round(template.target_duration_sec * SemanticValidator.WPM / 60)
        prompt = (
            f"Senaryo Şablonu: {template.name}\n"
            f"Hedef Süre: {template.target_duration_sec} sn\n"
            f"Hedef Kelime Sayısı: {target_words} (hook + body + cta toplamı, ±%10; "
            f"{SemanticValidator.WPM} kelime/dk ile seslendirilecek)\n"
            f"Maksimum Sahne: {template.max_scenes}\n"
            f"İzin Verilen Tonlar: {', '.join(template.allowed_tones)}\n\n"
            f"Bağlam (İçerik): {context}"
        )
        
        try:
            return await self._attempt_generation(prompt)
        except Exception as e:
            logger.error("script_gen_fatal", error=str(e), msg="Maksimum deneme (3) aşıldı! Senaryo üretilemedi.")
            detail = f"{type(e).__name__}: {str(e)[:500]}"
            raise ScriptGenerationError(
                f"Senaryo üretimi {template.name} için başarısız oldu. {detail}"
            ) from e
