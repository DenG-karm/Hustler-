"""Sidecar (gerçek main.app): token'sız/yanlış token istekleri reddedilir."""

import json
import os
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
async def test_events_with_wrong_token_returns_401_with_challenge(
    client: httpx.AsyncClient, token: str
) -> None:
    response = await client.get("/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["status"] == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


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


async def test_lifespan_initializes_db_cache_and_never_prints_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    async with main.lifespan(app):
        assert app.state.session_token == SESSION_TOKEN
        assert app.state.db is not None
        assert app.state.cache is not None
        assert (tmp_path / "hustler_core.db").exists()

    captured = capfd.readouterr()
    assert SESSION_TOKEN not in captured.out + captured.err
    assert "HUSTLER_BIND" not in captured.out + captured.err
    assert len(SESSION_TOKEN) >= 32


def test_token_is_taken_from_env_and_removed_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(main.TOKEN_ENV_VAR, "from-parent-process")

    assert main._load_session_token() == "from-parent-process"
    assert main.TOKEN_ENV_VAR not in os.environ  # alt süreçlere (ffmpeg) sızmaz


def test_token_falls_back_to_random_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(main.TOKEN_ENV_VAR, raising=False)

    first, second = main._load_session_token(), main._load_session_token()

    assert len(first) >= 32
    assert first != second


@pytest.mark.parametrize("raw", ["80", "abc", "70000", ""])
def test_resolve_port_rejects_invalid_env_values(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(main.PORT_ENV_VAR, raw)

    with pytest.raises(ValueError):
        main._resolve_port()


def test_resolve_port_uses_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(main.PORT_ENV_VAR, "45678")

    assert main._resolve_port() == 45678


async def test_unconfigured_app_rejects_everything_fail_closed(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app.state, "session_token", "", raising=False)

    response = await client.get("/events", headers={"Authorization": "Bearer "})

    assert response.status_code == 401


async def test_non_ascii_token_returns_401_not_500(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/events", headers={b"Authorization": "Bearer ş".encode("utf-8")}
    )

    assert response.status_code == 401


def test_free_port_helper_returns_valid_unprivileged_port() -> None:
    port = main._get_free_port()

    assert isinstance(port, int)
    assert 1024 <= port <= 65535
    assert json.dumps(port)
