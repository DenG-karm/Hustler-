"""Discovery route: gerçek sidecar/ağ yok; YouTube ve orkestratör sahtelenir."""

import time
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from services.core.hustler.api.routes import discovery as discovery_route
from services.core.hustler.api.routes.discovery import router

TOKEN = "unit-test-token"
URL = "/api/v1/discovery/run"
PAYLOAD = {"topic": "day trading smc", "max_results": 20, "score_threshold": 10.0}


class DiscoveryResult(BaseModel):
    fetched: int
    discarded: int
    inserted: int


class FakeYouTubeClient:
    def __init__(self, api_key: str, cache: object) -> None:
        self.api_key = api_key

    async def __aenter__(self) -> "FakeYouTubeClient":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        return None


class FakeOrchestrator:
    calls: list[tuple[str, int, float]] = []

    def __init__(self, youtube: object, db: object) -> None:
        pass

    async def init_tables(self) -> None:
        return None

    async def run_discovery(
        self, topic: str, max_results: int = 50, score_threshold: float = 30.0
    ) -> dict[str, int]:
        type(self).calls.append((topic, max_results, score_threshold))
        return {"fetched": 20, "discarded": 15, "inserted": 5}


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    FakeOrchestrator.calls = []
    monkeypatch.setenv("YOUTUBE_API_KEY", "fake-key")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.session_token = TOKEN
    app.state.db = object()
    app.state.cache = object()
    transport = httpx.ASGITransport(app=app)
    with (
        patch.object(discovery_route, "YouTubeClient", FakeYouTubeClient),
        patch.object(discovery_route, "DiscoveryOrchestrator", FakeOrchestrator),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_discovery_returns_expected_counts_with_valid_token(
    client: httpx.AsyncClient,
) -> None:
    start = time.perf_counter()
    response = await client.post(
        URL, json=PAYLOAD, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    result = DiscoveryResult.model_validate(response.json())
    assert result.fetched > 0
    assert result.fetched == result.discarded + result.inserted
    assert FakeOrchestrator.calls == [("day trading smc", 20, 10.0)]
    assert elapsed < 2.0


async def test_discovery_rejects_request_without_token_with_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(URL, json=PAYLOAD)

    assert response.status_code == 401
    assert FakeOrchestrator.calls == []


async def test_discovery_rejects_wrong_token_with_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        URL, json=PAYLOAD, headers={"Authorization": "Bearer wrong"}
    )

    assert response.status_code == 401
    assert FakeOrchestrator.calls == []


async def test_discovery_rejects_invalid_payload_with_422(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        URL,
        json={"max_results": "abc"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert FakeOrchestrator.calls == []


async def test_discovery_returns_500_when_api_key_missing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("YOUTUBE_API_KEY")

    response = await client.post(
        URL, json=PAYLOAD, headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 500
    assert "YOUTUBE_API_KEY" in response.json()["detail"]
