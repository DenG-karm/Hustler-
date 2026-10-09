"""InferencePort: gerçek ProcessPool; K-306 olay döngüsü gecikmesi ve cpu semaforu."""

import asyncio
import time
from itertools import count

import pytest

from services.core.hustler.infrastructure import inference
from services.core.hustler.infrastructure.inference import InferencePort


def test_worker_function_requires_initialized_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inference, "_MODEL_INSTANCE", None)

    with pytest.raises(RuntimeError, match="yüklenemedi"):
        inference._run_heavy_inference_sync("x")


def test_initializer_sets_model_and_worker_runs_to_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inference, "_MODEL_INSTANCE", None)
    inference._initialize_worker()
    clock = count(step=2.5)  # her çağrıda 2.5 sn ilerleyen sahte saat
    monkeypatch.setattr(time, "perf_counter", lambda: next(clock))

    out = inference._run_heavy_inference_sync("x")

    assert out.startswith("Çıkarım Başarılı! (Süre: ")
    assert inference._MODEL_INSTANCE == "STUB_MODEL"


@pytest.mark.slow
async def test_real_process_pool_does_not_block_event_loop() -> None:
    port = InferencePort(max_workers=1)
    gaps: list[float] = []

    async def pinger() -> None:
        last = time.perf_counter()
        while True:
            await asyncio.sleep(0.05)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    ping = asyncio.create_task(pinger())
    try:
        start = time.perf_counter()
        result = await asyncio.wait_for(port.run_inference("veri"), timeout=30)
        elapsed = time.perf_counter() - start
    finally:
        ping.cancel()
        await asyncio.gather(ping, return_exceptions=True)
        await asyncio.get_running_loop().run_in_executor(None, port.shutdown)

    assert result.startswith("Çıkarım Başarılı!")
    assert elapsed >= 5.0
    assert len(gaps) > 20
    assert max(gaps) < 0.5  # K-306: döngü gecikmesi sınırı
