import structlog
from typing import List

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec

logger = structlog.get_logger()

class SemanticValidationError(Exception):
    """Anlamsal doğrulama (süre, kopya vs.) başarısız olduğunda fırlatılır."""
    pass

class SemanticValidator:
    """
    K-404: Anlamsal Doğrulayıcı (Semantic Validator)
    Tamamen saf fonksiyondur (Pure Function). Veritabanına veya ağa erişmez.
    Üretilen senaryoların matematiksel ve anlamsal kısıtlara uymasını denetler.
    """
    WPM = 140
    TOLERANCE_PERCENT = 0.15
    NGRAM_SIZE = 4 # 4 kelimelik blokları kontrol edeceğiz

    @staticmethod
    def _extract_words(text: str) -> List[str]:
        """Metni noktalama işaretlerinden arındırıp kelime listesine çevirir."""
        import string
        clean = text.translate(str.maketrans('', '', string.punctuation)).lower()
        return clean.split()

    @classmethod
    def word_count(cls, *parts: str) -> int:
        """Do?rulay?c?n?n kulland??? kelime say?m? (noktalama hari?)."""
        return len(cls._extract_words(" ".join(parts)))

    @classmethod
    def validate(cls, script: ScriptDoc, template: TemplateSpec) -> bool:
        """
        Senaryoyu anlamsal olarak doğrular.
        Herhangi bir kural ihlalinde SemanticValidationError fırlatır.
        """
        full_text = script.hook + " " + " ".join(script.body) + " " + script.cta
        words = cls._extract_words(full_text)
        word_count = len(words)
        
        # --- Kural 1: Süre / Kelime Toleransı ---
        # 140 WPM varsayımıyla senaryonun seslendirme süresi
        estimated_duration = (word_count / cls.WPM) * 60
        target = template.target_duration_sec
        diff_percent = abs(estimated_duration - target) / target
        
        if diff_percent > cls.TOLERANCE_PERCENT:
            raise SemanticValidationError(
                f"Süre/Kelime toleransı aşıldı! Şablon Hedefi: {target}sn, "
                f"Hesaplanan Süre: {estimated_duration:.1f}sn (Sapma: %{diff_percent*100:.1f} > %{cls.TOLERANCE_PERCENT*100})"
            )
            
        # --- Kural 2: N-gram Tekrar (Halüsinasyon) Tespiti ---
        # LLM'lerin aynı paragrafı döndürüp durma hatasını yakalamak için 4 kelimelik pencereler arıyoruz.
        if len(words) >= cls.NGRAM_SIZE:
            seen_ngrams = set()
            for i in range(len(words) - cls.NGRAM_SIZE + 1):
                ngram = tuple(words[i:i+cls.NGRAM_SIZE])
                if ngram in seen_ngrams:
                    raise SemanticValidationError(
                        f"Metinde anlamsız n-gram tekrarı (LLM halüsinasyonu) tespit edildi: '{' '.join(ngram)}'"
                    )
                seen_ngrams.add(ngram)
                
        return True
