"""ScriptGenerator: gerçek retry/ayrıştırma mantığı; yalnızca LLM HTTP sınırı sahte."""

import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import ValidationError

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.generators.script_generator import (
    ScriptGenerationError,
    ScriptGenerator,
)

from services.core.hustler.infrastructure.llm_port import LLMHTTPError
from tests.conftest import LLMFactory

VALID = {
    "hook": "Dur!",
    "body": ["bir", "iki"],
    "cta": "Takip et",
    "estimated_duration": 25,
}


@pytest.fixture(autouse=True)
def _no_wait(fast_retry: Callable[[object], None]) -> None:
    fast_retry(ScriptGenerator._attempt_generation)


async def test_valid_json_returns_exact_script_doc(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    h = llm_factory([json.dumps(VALID)])

    doc = await ScriptGenerator(h.port).generate_script(template, "kedi videosu")

    assert doc == ScriptDoc.model_validate(VALID)
    assert len(h.prompts) == 1


async def test_prompt_contains_template_fields_and_schema(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    h = llm_factory([json.dumps(VALID)])

    await ScriptGenerator(h.port).generate_script(template, "BAGLAM-XYZ")

    p = h.prompts[0]
    assert "Senaryo Şablonu: Test" in p
    assert "Hedef Süre: 30 sn" in p
    assert "Hedef Kelime Sayısı: 70 " in p  # 30 sn * 140 WPM / 60
    assert "Maksimum Sahne: 3" in p
    assert "İzin Verilen Tonlar: ciddi" in p
    assert "Bağlam (İçerik): BAGLAM-XYZ" in p
    assert json.dumps(ScriptDoc.get_llm_schema(), ensure_ascii=False) in p


@pytest.mark.parametrize("fence", ["```json\n{}\n```", "```json\n{}```", "  {}  "])
async def test_markdown_fences_are_stripped(
    llm_factory: LLMFactory, template: TemplateSpec, fence: str
) -> None:
    h = llm_factory([fence.replace("{}", json.dumps(VALID))])

    doc = await ScriptGenerator(h.port).generate_script(template, "x")

    assert doc.hook == "Dur!"


async def test_recovers_after_two_broken_responses(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    h = llm_factory(["{bozuk", "düz metin", json.dumps(VALID)])

    doc = await ScriptGenerator(h.port).generate_script(template, "x")

    assert doc.estimated_duration == 25
    assert len(h.prompts) == 3


@pytest.mark.parametrize(
    "bad",
    [
        "{bozuk json",
        "",
        json.dumps({**VALID, "hook": "h" * 151}),
        json.dumps({**VALID, "body": []}),
        json.dumps({**VALID, "estimated_duration": 0}),
        json.dumps({"hook": "x"}),
    ],
)
async def test_persistently_invalid_output_raises_after_three_attempts(
    llm_factory: LLMFactory, template: TemplateSpec, bad: str
) -> None:
    h = llm_factory([bad])

    with pytest.raises(ScriptGenerationError) as exc:
        await ScriptGenerator(h.port).generate_script(template, "x")

    assert "Test" in str(exc.value)
    assert len(h.prompts) == 3
    assert isinstance(
        exc.value.__cause__, (ValidationError, json.JSONDecodeError, TypeError)
    )


async def test_non_retryable_error_is_wrapped_after_single_attempt(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    h = llm_factory([RuntimeError("ağ koptu")])

    with pytest.raises(ScriptGenerationError):
        await ScriptGenerator(h.port).generate_script(template, "x")

    assert len(h.prompts) == 1


async def test_10k_character_context_is_forwarded_intact(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    h = llm_factory([json.dumps(VALID)])
    context = "ş" * 10_000

    await ScriptGenerator(h.port).generate_script(template, context)

    assert context in h.prompts[0]


@pytest.mark.parametrize("raw", ["null", "[1, 2]", "42"])
async def test_non_object_json_is_wrapped_without_retry(
    llm_factory: LLMFactory, template: TemplateSpec, raw: str
) -> None:
    h = llm_factory([raw])

    with pytest.raises(ScriptGenerationError) as exc:
        await ScriptGenerator(h.port).generate_script(template, "x")

    assert isinstance(exc.value.__cause__, TypeError)
    assert len(h.prompts) == 1


async def test_http_error_detail_is_not_masked(
    llm_factory: LLMFactory, template: TemplateSpec
) -> None:
    resp = httpx.Response(
        404,
        json={"error": {"message": "model gone"}},
        request=httpx.Request("POST", "https://example.test/x"),
    )
    h = llm_factory([LLMHTTPError(resp)])

    with pytest.raises(ScriptGenerationError) as info:
        await ScriptGenerator(h.port).generate_script(template, "x")

    assert "LLMHTTPError" in str(info.value)
    assert "404" in str(info.value) and "model gone" in str(info.value)
    assert isinstance(info.value.__cause__, LLMHTTPError)
    assert len(h.prompts) == 1
