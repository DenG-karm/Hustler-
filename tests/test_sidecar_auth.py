"""Sidecar (gerçek main.app): token'sız/yanlış token istekleri reddedilir."""

import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from services.core.hustler import main
from services.core.hustler.main import SESSION_TOKEN, app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_events_without_token_returns_401_problem_details(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/events")

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401
    assert body["type"] == "https://hustler.local/errors/401"
    assert body["instance"] == "/events"
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "header", ["", "Basic abc", "Bearer", "bearer lower", "Token x"]
)
async def test_events_with_malformed_authorization_header_returns_401(
    client: httpx.AsyncClient, header: str
) -> None:
    response = await client.get("/events", headers={"Authorization": header})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token", ["wrong", "", SESSION_TOKEN[:-1], SESSION_TOKEN + "x", "x" * 10_000]
)
async def test_events_with_wrong_token_returns_403(
    client: httpx.AsyncClient, token: str
) -> None:
    response = await client.get("/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["status"] == 403


async def test_events_with_valid_token_streams_connected_event(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        "/events", headers={"Authorization": f"Bearer {SESSION_TOKEN}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == "data: connected\n\n"


async def test_discovery_route_on_real_app_without_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/v1/discovery/run", json={"topic": "x"})

    assert response.status_code == 401


async def test_health_is_public_and_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_lifespan_initializes_db_cache_and_announces_bind_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    app.state.bind_port = 4242

    async with main.lifespan(app):
        assert app.state.session_token == SESSION_TOKEN
        assert app.state.db is not None
        assert app.state.cache is not None
        assert (tmp_path / "hustler_core.db").exists()

    out = capsys.readouterr().out
    match = re.search(r"HUSTLER_BIND::PORT=(\d+)::TOKEN=([\w-]+)", out)
    assert match is not None
    assert match.group(1) == "4242"
    assert match.group(2) == SESSION_TOKEN
    assert len(SESSION_TOKEN) >= 32


def test_free_port_helper_returns_valid_unprivileged_port() -> None:
    port = main._get_free_port()

    assert isinstance(port, int)
    assert 1024 <= port <= 65535
    assert json.dumps(port)
