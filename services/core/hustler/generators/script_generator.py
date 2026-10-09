import json
import structlog
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from pydantic import ValidationError

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.infrastructure.llm_port import LLMPort
from services.core.hustler.validation.semantic import SemanticValidationError, SemanticValidator

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
    def __init__(
        self,
        llm_port: LLMPort,
        validate_semantics: bool = False,
        max_semantic_attempts: int = 4,
    ):
        """
        validate_semantics=True: ?retilen senaryo SemanticValidator'dan ge?mezse ret nedeni
        (kelime say?s? dahil) LLM'e geri bildirilip yeniden ?retilir (en fazla max_semantic_attempts).
        """
        self.llm_port = llm_port
        self.validate_semantics = validate_semantics
        self.max_semantic_attempts = max_semantic_attempts
        self.semantic_attempts = 0

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
            f"Da??l?m: hook ?150 karakter (~15 kelime), cta ?100 karakter (~12 kelime), "
            f"kalan ~{max(target_words - 27, 1)} kelime body ??elerinde (en az 6 ??e).\n"
            f"Maksimum Sahne: {template.max_scenes}\n"
            f"İzin Verilen Tonlar: {', '.join(template.allowed_tones)}\n\n"
            f"Bağlam (İçerik): {context}"
        )
        
        try:
            if not self.validate_semantics:
                return await self._attempt_generation(prompt)
            return await self._generate_with_semantic_feedback(prompt, template, target_words)
        except Exception as e:
            logger.error("script_gen_fatal", error=str(e), msg="Maksimum deneme a??ld?! Senaryo ?retilemedi.")
            detail = f"{type(e).__name__}: {str(e)[:500]}"
            raise ScriptGenerationError(
                f"Senaryo ?retimi {template.name} i?in ba?ar?s?z oldu. {detail}"
            ) from e

    @staticmethod
    def _describe_rejection(error: Exception) -> str:
        """Ret nedenini LLM'e k?sa ve okunur bi?imde aktar?r."""
        if isinstance(error, ValidationError):
            return "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in error.errors()
            )
        if isinstance(error, json.JSONDecodeError):
            return f"Ge?erli JSON de?il ({error.msg})"
        return str(error)

    async def _generate_with_semantic_feedback(
        self, prompt: str, template: TemplateSpec, target_words: int
    ) -> ScriptDoc:
        """
        ?ema/JSON/anlamsal ret nedenini LLM'e geri besleyerek yeniden ?retir.
        Her denemede istek tek seferliktir (ayn? prompt'u k?r? k?r?ne tekrarlamaz);
        son denemede hata f?rlat?l?r.
        """
        attempt_once = self._attempt_generation.retry_with(stop=stop_after_attempt(1))
        current_prompt = prompt
        self.semantic_attempts = 0
        while True:
            self.semantic_attempts += 1
            words: int | None = None
            try:
                doc = await attempt_once(self, current_prompt)
                words = SemanticValidator.word_count(doc.hook, *doc.body, doc.cta)
                SemanticValidator.validate(doc, template)
                return doc
            except (SemanticValidationError, ValidationError, json.JSONDecodeError) as e:
                if self.semantic_attempts >= self.max_semantic_attempts:
                    raise
                reason = self._describe_rejection(e)
                logger.warning(
                    "script_gen_feedback_retry", attempt=self.semantic_attempts,
                    target_words=target_words, reason=reason,
                )
                hint = ""
                if words is not None:
                    direction = "daha uzun" if words < target_words else "daha k?sa"
                    delta = abs(target_words - words)
                    hint = (
                        f"?nceki metin {words} kelimeydi; hedef {target_words} kelime "
                        f"({direction} yazmal?s?n, yakla??k {delta} kelime fark).\n"
                    )
                current_prompt = (
                    f"{prompt}\n\n?NCEK? DENEME REDDED?LD?: {reason}\n{hint}"
                    f"Alan s?n?rlar?na (hook ?150, cta ?100 karakter) ve hedef kelime say?s?na "
                    f"({target_words}) uyan yeni bir senaryo ?ret."
                )
