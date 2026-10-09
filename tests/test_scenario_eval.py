"""ScenarioEvaluationEngine: gerçek Pydantic + semantik + iddia hattı; yalnızca LLM sınırı sahte."""

import json

import pytest
from tests.conftest import LLMFactory
from tests.test_semantic_validator import CLEAN_BODY

from services.core.hustler.evaluation.scenario_eval import ScenarioEvaluationEngine
from services.core.hustler.validation.claims import ClaimMarker

GOOD = {
    "hook": "Temiz başlangıç kancası",
    "body": [CLEAN_BODY],
    "cta": "Abone ol dostum",
    "estimated_duration": 30,
}
SAFE = json.dumps({"is_safe": True, "flagged_claims": [], "risk_level": "LOW"})


def _case(
    raw: object, res: str, stage: str | None, cid: str = "c"
) -> dict[str, object]:
    return {
        "id": cid,
        "raw_data": raw,
        "expected_result": res,
        "expected_failure_stage": stage,
    }


def _engine(
    llm_factory: LLMFactory, reply: str = SAFE
) -> tuple[ScenarioEvaluationEngine, list[str]]:
    h = llm_factory([reply])
    return ScenarioEvaluationEngine(ClaimMarker(h.port)), h.prompts


async def test_valid_safe_script_passes_all_three_stages(
    llm_factory: LLMFactory,
) -> None:
    engine, prompts = _engine(llm_factory)

    r = await engine.evaluate_single(_case(GOOD, "PASS", None, "ok"))

    assert (r.scenario_id, r.actual_result, r.actual_failure_stage) == (
        "ok",
        "PASS",
        None,
    )
    assert r.is_correct and r.passed and r.error_msg == ""
    assert len(prompts) == 1
    assert "Temiz başlangıç kancası" in prompts[0] and "Abone ol dostum" in prompts[0]


async def test_schema_violation_stops_at_pydantic_before_llm(
    llm_factory: LLMFactory,
) -> None:
    engine, prompts = _engine(llm_factory)

    r = await engine.evaluate_single(_case({"hook": "x"}, "FAIL", "K-401_PYDANTIC"))

    assert r.actual_failure_stage == "K-401_PYDANTIC" and r.is_correct
    assert "validation error" in r.error_msg
    assert prompts == []


async def test_semantic_failure_stops_before_llm(llm_factory: LLMFactory) -> None:
    engine, prompts = _engine(llm_factory)
    short = {**GOOD, "body": ["çok kısa"]}

    r = await engine.evaluate_single(_case(short, "FAIL", "K-404_SEMANTIC"))

    assert r.actual_failure_stage == "K-404_SEMANTIC" and r.is_correct
    assert "toleransı aşıldı" in r.error_msg
    assert prompts == []


@pytest.mark.parametrize(
    ("is_safe", "risk"), [(False, "LOW"), (True, "HIGH"), (True, "MEDIUM")]
)
async def test_claim_rejection_or_review_fails_at_claim_stage(
    llm_factory: LLMFactory, is_safe: bool, risk: str
) -> None:
    reply = json.dumps(
        {"is_safe": is_safe, "flagged_claims": ["x"], "risk_level": risk}
    )
    engine, _ = _engine(llm_factory, reply)

    r = await engine.evaluate_single(_case(GOOD, "FAIL", "K-405_CLAIM"))

    assert r.actual_failure_stage == "K-405_CLAIM" and r.is_correct
    assert r.error_msg == f"Rejected with risk: {risk}"


async def test_wrong_expectation_is_marked_incorrect(llm_factory: LLMFactory) -> None:
    engine, _ = _engine(llm_factory)

    r = await engine.evaluate_single(_case(GOOD, "FAIL", "K-405_CLAIM"))

    assert r.actual_result == "PASS"
    assert not r.is_correct and not r.passed


async def test_run_evaluation_computes_accuracy(llm_factory: LLMFactory) -> None:
    engine, _ = _engine(llm_factory)
    dataset = [
        _case(GOOD, "PASS", None, "1"),
        _case({"hook": "x"}, "FAIL", "K-401_PYDANTIC", "2"),
        _case({"hook": "x"}, "PASS", None, "3"),  # yanlış beklenti
        _case({**GOOD, "body": ["kısa"]}, "FAIL", "K-404_SEMANTIC", "4"),
    ]

    out = await engine.run_evaluation(dataset)

    assert out["total"] == 4 and out["correct"] == 3
    assert out["accuracy"] == 75.0
    assert [r.scenario_id for r in out["results"]] == ["1", "2", "3", "4"]


async def test_empty_dataset_has_zero_accuracy(llm_factory: LLMFactory) -> None:
    engine, _ = _engine(llm_factory)

    out = await engine.run_evaluation([])

    assert out == {"accuracy": 0, "total": 0, "correct": 0, "results": []}


async def test_case_missing_required_key_raises(llm_factory: LLMFactory) -> None:
    engine, _ = _engine(llm_factory)

    with pytest.raises(KeyError):
        await engine.evaluate_single({"id": "x"})


async def test_broken_llm_json_in_claim_stage_must_not_count_as_pass(
    llm_factory: LLMFactory,
) -> None:
    engine, _ = _engine(llm_factory, "{bozuk")

    r = await engine.evaluate_single(_case(GOOD, "PASS", None))

    assert r.actual_result != "PASS"
