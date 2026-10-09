"""Reduce: içerik-hash önbelleği; LLM sahte, DB geçici (tmp_path) SQLite."""

import time
from dataclasses import dataclass
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

import pytest
from pydantic import BaseModel

from services.core.hustler.db import Database
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse
from services.core.hustler.orchestration.reduce import ReduceOrchestrator

TRANSCRIPT = "Bu çok çok önemli bir YouTube Shorts videosunun transkript metnidir."


class AnalysisResult(BaseModel):
    text: str
    tokens_used: int
    prompt_version: str


@dataclass
class Harness:
    engine: ReduceOrchestrator
    llm: LLMPort
    prompts: list[str]


@pytest.fixture
async def harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Harness]:
    db = Database(tmp_path / "reduce.sqlite")
    await db.init()
    llm = LLMPort(api_key="fake", max_tokens=10_000)
    prompts: list[str] = []

    async def fake(prompt: str) -> LLMResponse:
        prompts.append(prompt)
        return LLMResponse("Sentetik Reduce Analizi", 10, 10, 20)

    monkeypatch.setattr(llm, "_execute_network_request", fake)
    engine = ReduceOrchestrator(db, llm)
    await engine.init_table()
    try:
        yield Harness(engine=engine, llm=llm, prompts=prompts)
    finally:
        await db.close()
        await llm.close()


async def test_first_request_is_cache_miss_and_calls_llm_once(harness: Harness) -> None:
    start = time.perf_counter()
    res = AnalysisResult.model_validate(
        await harness.engine.analyze(TRANSCRIPT, "v1.2")
    )
    elapsed = time.perf_counter() - start

    assert len(harness.prompts) == 1
    assert res.text == "Sentetik Reduce Analizi"
    assert res.tokens_used == 20
    assert res.prompt_version == "v1.2"
    assert harness.llm.ledger.current_usage == 20
    assert elapsed < 2.0


async def test_identical_second_request_is_cache_hit_with_zero_tokens(
    harness: Harness,
) -> None:
    first = await harness.engine.analyze(TRANSCRIPT, "v1.2")
    second = await harness.engine.analyze(TRANSCRIPT, "v1.2")

    assert len(harness.prompts) == 1
    assert harness.llm.ledger.current_usage == 20
    assert second == first


async def test_changed_prompt_version_invalidates_cache(harness: Harness) -> None:
    await harness.engine.analyze(TRANSCRIPT, "v1.0")
    await harness.engine.analyze(TRANSCRIPT, "v2.0")

    assert len(harness.prompts) == 2


async def test_different_transcript_is_a_cache_miss(harness: Harness) -> None:
    await harness.engine.analyze(TRANSCRIPT, "v1.0")
    await harness.engine.analyze(TRANSCRIPT + " Farklı.", "v1.0")

    assert len(harness.prompts) == 2


async def test_llm_failure_propagates_and_is_not_cached(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    failure: Optional[Exception] = RuntimeError("llm down")

    async def flaky(prompt: str) -> LLMResponse:
        calls.append(1)
        if failure is not None and len(calls) == 1:
            raise failure
        return LLMResponse("ok", 1, 1, 2)

    monkeypatch.setattr(harness.llm, "_execute_network_request", flaky)

    with pytest.raises(RuntimeError, match="llm down"):
        await harness.engine.analyze("x", "v1")
    res = await harness.engine.analyze("x", "v1")

    assert res["text"] == "ok"
    assert len(calls) == 2
