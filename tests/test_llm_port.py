"""LLMPort: ağ isteği sahtelenir; bütçe fail-fast ve HTTP davranışı doğrulanır."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from services.core.hustler.infrastructure.llm_port import (
    LLMPort,
    LLMResponse,
    TokenLimitExceededError,
)


@pytest.fixture
async def port() -> AsyncIterator[LLMPort]:
    p = LLMPort(api_key="fake-key", max_tokens=15)
    yield p
    await p.close()


async def _port_with_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> LLMPort:
    p = LLMPort(api_key="fake-key", max_tokens=100)
    await p.client.aclose()
    p.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return p


async def test_generate_text_records_token_usage_in_ledger(
    port: LLMPort, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake(prompt: str) -> LLMResponse:
        return LLMResponse("ok", 5, 5, 10)

    monkeypatch.setattr(port, "_execute_network_request", fake)

    res = await port.generate_text("merhaba")

    assert isinstance(res, LLMResponse)
    assert len(res.text) > 0
    assert res.total_tokens == 10
    assert port.ledger.current_usage == 10


async def test_generate_text_blocks_without_network_when_budget_exhausted(
    port: LLMPort, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake(prompt: str) -> LLMResponse:
        calls.append(prompt)
        return LLMResponse("ok", 5, 5, 10)

    monkeypatch.setattr(port, "_execute_network_request", fake)

    await port.generate_text("1")  # kullanım 10 < 15: geçer
    await port.generate_text("2")  # kullanım 20 >= 15 olur
    with pytest.raises(TokenLimitExceededError):
        await port.generate_text("3")

    assert len(calls) == 2


async def test_generate_text_parses_gemini_response_via_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "Mavi"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 1,
                    "totalTokenCount": 4,
                },
            },
        )

    port = await _port_with_transport(handler)
    try:
        start = time.perf_counter()
        res = await asyncio.wait_for(port.generate_text("renk?"), timeout=5)
        elapsed = time.perf_counter() - start
    finally:
        await port.close()

    assert res == LLMResponse("Mavi", 3, 1, 4)
    assert port.ledger.current_usage == 4
    assert elapsed < 2.0


async def test_generate_text_raises_and_charges_nothing_on_http_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(401, json={"error": "unauthorized"})

    async def no_sleep(_: float) -> None:
        return None

    # tenacity bekleme sürelerini (2-10 sn) testte atla
    monkeypatch.setattr(LLMPort._execute_network_request.retry, "sleep", no_sleep)
    port = await _port_with_transport(handler)
    try:
        with pytest.raises(Exception) as info:
            await asyncio.wait_for(port.generate_text("x"), timeout=5)
    finally:
        await port.close()

    assert len(attempts) >= 1
    assert type(info.value).__name__ in {"RetryError", "HTTPStatusError"}
    assert port.ledger.current_usage == 0
