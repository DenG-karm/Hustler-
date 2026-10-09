"""LLMPort: ağ isteği sahtelenir; bütçe fail-fast ve HTTP davranışı doğrulanır."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from services.core.hustler.infrastructure.llm_port import (
    GEMINI_MODEL,
    LLMHTTPError,
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
    port: LLMPort,
    monkeypatch: pytest.MonkeyPatch,
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

    assert len(attempts) == 1  # 401 kal?c? hatad?r: yeniden denenmez
    assert isinstance(info.value, LLMHTTPError)
    assert info.value.response.status_code == 401
    assert "401" in str(info.value) and "unauthorized" in str(info.value)
    assert port.ledger.current_usage == 0


async def test_api_key_goes_in_header_not_in_url() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]})

    port = await _port_with_transport(handler)
    try:
        await asyncio.wait_for(port.generate_text("selam"), timeout=5)
    finally:
        await port.close()

    req = seen[0]
    assert req.headers["x-goog-api-key"] == "fake-key"
    assert "fake-key" not in str(req.url)
    assert req.url.query == b""
    assert GEMINI_MODEL == "gemini-2.5-flash"
    assert f"/models/{GEMINI_MODEL}:generateContent" in str(req.url)


async def test_404_error_exposes_status_and_body_without_retry() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    port = await _port_with_transport(handler)
    try:
        with pytest.raises(LLMHTTPError, match="404.*model not found"):
            await asyncio.wait_for(port.generate_text("x"), timeout=5)
    finally:
        await port.close()

    assert len(attempts) == 1


async def test_503_is_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(LLMPort._execute_network_request.retry, "sleep", no_sleep)
    port = await _port_with_transport(handler)
    try:
        res = await asyncio.wait_for(port.generate_text("x"), timeout=5)
    finally:
        await port.close()

    assert res.text == "ok"
    assert len(attempts) == 3
