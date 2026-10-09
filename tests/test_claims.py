"""ClaimReport / ScriptStatusDecider / ClaimMarker gerçek mantığı."""

import json

import pytest
from pydantic import ValidationError

from services.core.hustler.validation.claims import (
    ClaimMarker,
    ClaimReport,
    ScriptStatusDecider,
)

from tests.conftest import LLMFactory


@pytest.mark.parametrize(
    ("is_safe", "risk", "expected"),
    [
        (True, "LOW", "APPROVED"),
        (True, "MEDIUM", "PENDING_REVIEW"),
        (True, "HIGH", "REJECTED"),
        (False, "LOW", "REJECTED"),
        (False, "MEDIUM", "REJECTED"),
        (False, "HIGH", "REJECTED"),
    ],
)
def test_status_decision_matrix(is_safe: bool, risk: str, expected: str) -> None:
    report = ClaimReport.model_validate(
        {"is_safe": is_safe, "flagged_claims": [], "risk_level": risk}
    )

    assert ScriptStatusDecider.get_final_status(report) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"is_safe": True, "flagged_claims": [], "risk_level": "CRITICAL"},
        {"is_safe": "belki", "flagged_claims": [], "risk_level": "LOW"},
        {"flagged_claims": [], "risk_level": "LOW"},
        {"is_safe": True, "flagged_claims": "x", "risk_level": "LOW"},
    ],
)
def test_claim_report_rejects_invalid_payload(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClaimReport.model_validate(payload)


async def test_verify_claims_parses_report_and_sends_text_and_schema(
    llm_factory: LLMFactory,
) -> None:
    body = {"is_safe": False, "flagged_claims": ["%500 kazanç"], "risk_level": "HIGH"}
    h = llm_factory([f"```json\n{json.dumps(body)}\n```"])

    report = await ClaimMarker(h.port).verify_claims("Garantili %500 kazanç")

    assert report == ClaimReport.model_validate(body)
    assert "METİN:\nGarantili %500 kazanç" in h.prompts[0]
    assert (
        json.dumps(ClaimReport.model_json_schema(), ensure_ascii=False) in h.prompts[0]
    )


async def test_verify_claims_plain_json_without_fence(llm_factory: LLMFactory) -> None:
    body = {"is_safe": True, "flagged_claims": [], "risk_level": "LOW"}
    h = llm_factory([json.dumps(body)])

    report = await ClaimMarker(h.port).verify_claims("temiz")

    assert ScriptStatusDecider.get_final_status(report) == "APPROVED"


@pytest.mark.parametrize(
    ("raw", "exc"),
    [
        ("{bozuk", json.JSONDecodeError),
        ("", json.JSONDecodeError),
        ('{"is_safe": true}', ValidationError),
        (
            '{"is_safe": true, "flagged_claims": [], "risk_level": "??"}',
            ValidationError,
        ),
    ],
)
async def test_verify_claims_bad_llm_output_raises(
    llm_factory: LLMFactory, raw: str, exc: type[Exception]
) -> None:
    h = llm_factory([raw])

    with pytest.raises(exc):
        await ClaimMarker(h.port).verify_claims("x")


async def test_verify_claims_10k_char_script_is_forwarded(
    llm_factory: LLMFactory,
) -> None:
    h = llm_factory(['{"is_safe": true, "flagged_claims": [], "risk_level": "LOW"}'])
    text = "a" * 10_000

    await ClaimMarker(h.port).verify_claims(text)

    assert text in h.prompts[0]
