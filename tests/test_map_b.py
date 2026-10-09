"""MapBExecutor: gerçek batch/semaphore/izolasyon mantığı; LLM ve inference sınırı sahte."""

import asyncio

import pytest

from services.core.hustler.infrastructure.inference import InferencePort
from services.core.hustler.orchestration.map_b import MapBExecutor

from services.core.hustler.infrastructure.llm_port import LLMResponse
from tests.conftest import LLMFactory


class FakeInference(InferencePort):
    def __init__(self) -> None:  # süreç havuzu açılmaz
        self.seen: list[str] = []

    async def run_inference(self, text: str) -> str:
        self.seen.append(text)
        if text == "boom":
            raise ValueError("model patladı")
        return f"yerel:{text}"


async def test_api_mode_success_for_each_video(llm_factory: LLMFactory) -> None:
    h = llm_factory(["KANCA"])

    out = await MapBExecutor(llm_port=h.port).execute_batch(
        [{"video_id": "a", "transcript": "t1"}, {"video_id": "b", "transcript": "t2"}]
    )

    assert out == [
        {"video_id": "a", "result": "KANCA", "mode": "api_llm", "status": "SUCCESS"},
        {"video_id": "b", "result": "KANCA", "mode": "api_llm", "status": "SUCCESS"},
    ]
    assert sorted(h.prompts) == [
        "Bu metinden kancayı çıkar: t1",
        "Bu metinden kancayı çıkar: t2",
    ]


async def test_partial_failure_is_isolated(llm_factory: LLMFactory) -> None:
    h = llm_factory([RuntimeError("limit"), "OK"])

    out = await MapBExecutor(llm_port=h.port).execute_batch(
        [{"video_id": "a", "transcript": "x"}, {"video_id": "b", "transcript": "y"}]
    )

    assert [o["status"] for o in out] == ["FAILED", "SUCCESS"]
    assert out[0] == {"video_id": "a", "error": "limit", "status": "FAILED"}


async def test_local_mode_uses_inference_port() -> None:
    fake = FakeInference()

    out = await MapBExecutor(inference_port=fake).execute_batch(
        [
            {"video_id": "a", "transcript": "ok"},
            {"video_id": "b", "transcript": "boom"},
        ],
        use_local_model=True,
    )

    assert out[0] == {
        "video_id": "a",
        "result": "yerel:ok",
        "mode": "local_inference",
        "status": "SUCCESS",
    }
    assert out[1] == {"video_id": "b", "error": "model patladı", "status": "FAILED"}


@pytest.mark.parametrize("local", [True, False])
async def test_missing_port_is_reported_as_failure(local: bool) -> None:
    out = await MapBExecutor().execute_batch(
        [{"video_id": "a", "transcript": "x"}], use_local_model=local
    )

    assert out[0]["status"] == "FAILED"
    assert "yapılandırılmadı" in str(out[0]["error"])


async def test_empty_batch_returns_empty_list() -> None:
    assert await MapBExecutor().execute_batch([]) == []


async def test_api_concurrency_never_exceeds_five(
    llm_factory: LLMFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = llm_factory(["x"])
    active = peak = 0
    real = h.port.generate_text

    async def tracked(prompt: str) -> LLMResponse:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        try:
            return await real(prompt)
        finally:
            active -= 1

    monkeypatch.setattr(h.port, "generate_text", tracked)

    out = await MapBExecutor(llm_port=h.port).execute_batch(
        [{"video_id": str(i), "transcript": "t"} for i in range(12)]
    )

    assert len(out) == 12 and all(o["status"] == "SUCCESS" for o in out)
    assert peak == 5
