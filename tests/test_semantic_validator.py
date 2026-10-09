"""SemanticValidator: süre toleransı ve n-gram tekrar tespiti (saf fonksiyon)."""

import pytest

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import RenderConfig, SafeZone, TemplateSpec
from services.core.hustler.validation.semantic import (
    SemanticValidationError,
    SemanticValidator,
)

CLEAN_BODY = (
    "Bu birinci cümle tamamen rastgele olarak yazılıyor ve uzun tutuluyor. "
    "İkinci kısımda tekrara düşmemeye özen gösteriyorum ki sistem hata vermesin. "
    "Üçüncü adım yapay zekanın gelişmiş analitik yeteneklerini anlatır ve detaylandırır. "
    "Dördüncü satır başka bir dünyayı inanılmaz bir görsellikle betimliyor. "
    "Beşinci bölümde işler daha da karmaşıklaşıyor, senaryo çok ilginç bir hal alıyor. "
    "Altıncı cümlenin sonuna doğru toplam kelime sayımız yetmiş hedefine yaklaşıyor. "
    "Kapanışta herkes mutlu mesut bir şekilde videodan harika bir deneyimle ayrılıyor."
)


@pytest.fixture
def template() -> TemplateSpec:
    zone = SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10)
    return TemplateSpec(
        name="Test",
        target_duration_sec=30,
        max_scenes=3,
        allowed_tones=["ciddi"],
        render_config=RenderConfig(
            width=1080, height=1920, fps=30, bg_color="#000", safe_zone=zone
        ),
    )


def _script(body: str, hook: str = "Temiz başlangıç kancası", cta: str = "Abone ol dostum") -> ScriptDoc:
    return ScriptDoc(hook=hook, body=[body], cta=cta, estimated_duration=30)


def test_clean_script_within_tolerance_passes(template: TemplateSpec) -> None:
    assert SemanticValidator.validate(_script(CLEAN_BODY), template) is True


def test_too_short_script_raises_duration_error(template: TemplateSpec) -> None:
    script = _script("Sadece birkaç kelime yazdım ve bitti.", "Kısa kanca", "Kapanış")

    with pytest.raises(SemanticValidationError, match="toleransı aşıldı"):
        SemanticValidator.validate(script, template)


def test_too_long_script_raises_duration_error(template: TemplateSpec) -> None:
    script = _script(CLEAN_BODY + " " + CLEAN_BODY)

    with pytest.raises(SemanticValidationError, match="toleransı aşıldı"):
        SemanticValidator.validate(script, template)


def test_repeated_ngram_block_is_detected_as_hallucination(template: TemplateSpec) -> None:
    script = _script("ben iyi bir yapay zekayım. " * 14, "Tekrar kancası", "Kapanış kısmı")

    with pytest.raises(SemanticValidationError, match="n-gram"):
        SemanticValidator.validate(script, template)


def test_punctuation_and_case_are_ignored_when_counting_words() -> None:
    words = SemanticValidator._extract_words("Merhaba, DÜNYA! Nasılsın?")

    assert words == ["merhaba", "dünya", "nasılsın"]
