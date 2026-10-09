"""EvalHarness: gerçek puanlama mantığı; LLM HTTP sınırı sahte, veri seti tmp_path'te."""

import json
from pathlib import Path

import pytest
from tests.conftest import LLMFactory

from services.core.hustler.evaluation.harness import EvalHarness

IDEAL = {"has_hook": True, "hook_text": "linke tıklayın", "topic": "finans"}


def _dataset(tmp_path: Path, items: list[dict[str, object]]) -> str:
    p = tmp_path / "ds.json"
    p.write_text(json.dumps(items), encoding="utf-8")
    return str(p)


@pytest.fixture
def harness(tmp_path: Path, llm_factory: LLMFactory) -> EvalHarness:
    return EvalHarness(_dataset(tmp_path, []), llm_factory(["{}"]).port)


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (dict(IDEAL), 100.0),
        ("düz metin", 0.0),
        ({}, 0.0),
        ({**IDEAL, "has_hook": False}, 66.67),
        ({**IDEAL, "has_hook": "True"}, 66.67),  # tip uyuşmazlığı cezası
        (
            {**IDEAL, "hook_text": "LINKE TIKLAYIN"},
            93.33,
        ),  # Python I.lower()=i (ı değil) → yalnızca 4 harf önek toleransı (%80)
        ({**IDEAL, "hook_text": "Linke Tıklayın!"}, 100.0),  # ideal, gerçeğin içinde
        ({**IDEAL, "hook_text": "link"}, 100.0),  # gerçek, idealin içinde
        ({**IDEAL, "hook_text": "linkedin"}, 93.33),  # 4 harf önek toleransı (%80)
        ({**IDEAL, "topic": "spor"}, 66.67),
        ({"has_hook": True}, 33.33),
    ],
)
def test_compare_scoring(harness: EvalHarness, actual: object, expected: float) -> None:
    assert harness._compare(IDEAL, actual) == pytest.approx(expected, abs=0.01)  # type: ignore[arg-type]


def test_compare_empty_string_rules(harness: EvalHarness) -> None:
    ideal = {"has_hook": False, "hook_text": "", "topic": ""}

    assert (
        harness._compare(ideal, {"has_hook": False, "hook_text": "", "topic": ""})
        == 100.0
    )
    assert (
        harness._compare(ideal, {"has_hook": False, "hook_text": "x", "topic": ""})
        == 66.67
    )


def test_missing_dataset_file_raises(tmp_path: Path, llm_factory: LLMFactory) -> None:
    with pytest.raises(FileNotFoundError):
        EvalHarness(str(tmp_path / "yok.json"), llm_factory(["{}"]).port)


def test_corrupt_dataset_file_raises(tmp_path: Path, llm_factory: LLMFactory) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{bozuk", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        EvalHarness(str(p), llm_factory(["{}"]).port)


async def test_evaluate_prompt_averages_and_injects_transcript(
    tmp_path: Path, llm_factory: LLMFactory
) -> None:
    items: list[dict[str, object]] = [
        {"transcript": "T-ONE", "ideal_output": IDEAL},
        {"transcript": "T-TWO", "ideal_output": IDEAL},
    ]
    h = llm_factory([json.dumps(IDEAL), "JSON değil"])
    harness = EvalHarness(_dataset(tmp_path, items), h.port)

    score = await harness.evaluate_prompt("Analiz: {{TRANSCRIPT}}")

    assert h.prompts == ["Analiz: T-ONE", "Analiz: T-TWO"]
    assert score == 50.0  # (100 + 0) / 2


async def test_regression_reports_negative_delta(
    tmp_path: Path, llm_factory: LLMFactory
) -> None:
    items: list[dict[str, object]] = [{"transcript": "t", "ideal_output": IDEAL}]
    h = llm_factory([json.dumps(IDEAL), "bozuk"])
    harness = EvalHarness(_dataset(tmp_path, items), h.port)

    v1, v2, delta = await harness.run_regression_test(
        "iyi {{TRANSCRIPT}}", "kötü {{TRANSCRIPT}}"
    )

    assert (v1, v2, delta) == (100.0, 0.0, -100.0)


async def test_dataset_item_missing_key_raises(
    tmp_path: Path, llm_factory: LLMFactory
) -> None:
    harness = EvalHarness(
        _dataset(tmp_path, [{"transcript": "x"}]), llm_factory(["{}"]).port
    )

    with pytest.raises(KeyError):
        await harness.evaluate_prompt("{{TRANSCRIPT}}")
