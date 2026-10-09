"""Gerçek sidecar süreci: Rust'ın kullandığı başlatma sözleşmesi (env + modül yolu) uçtan uca."""

import asyncio
import os
import socket
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN = "integration-test-token-0123456789abcdef"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
async def sidecar(tmp_path: Path) -> AsyncIterator[tuple[int, asyncio.subprocess.Process]]:
    port = _free_port()
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "HUSTLER_SESSION_TOKEN": TOKEN,
        "HUSTLER_PORT": str(port),
    }
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "services.core.hustler.main",
        cwd=tmp_path,  # hustler_core.db testin geçici dizinine yazılır
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 20
        async with httpx.AsyncClient() as c:
            while time.monotonic() < deadline:
                if proc.returncode is not None:
                    assert proc.stderr is not None
                    pytest.fail(f"sidecar erken öldü: {(await proc.stderr.read()).decode(errors='replace')[-600:]}")
                try:
                    if (await c.get(f"http://127.0.0.1:{port}/health")).status_code == 200:
                        break
                except httpx.TransportError:
                    await asyncio.sleep(0.1)
            else:
                pytest.fail("sidecar /health yanıtı vermedi")
        yield port, proc
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()


async def test_real_sidecar_enforces_bearer_auth_and_never_prints_token(
    sidecar: tuple[int, asyncio.subprocess.Process],
) -> None:
    port, proc = sidecar
    base = f"http://127.0.0.1:{port}"
    async with httpx.AsyncClient() as c:
        missing = await c.get(f"{base}/events")
        wrong = await c.get(f"{base}/events", headers={"Authorization": "Bearer nope"})
        async with c.stream(
            "GET", f"{base}/events", headers={"Authorization": f"Bearer {TOKEN}"}
        ) as ok:
            ok_status = ok.status_code

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert "invalid_token" in wrong.headers["www-authenticate"]
    assert ok_status == 200

    proc.kill()
    assert proc.stdout is not None and proc.stderr is not None
    output = (await proc.stdout.read()) + (await proc.stderr.read())
    assert TOKEN.encode() not in output
    assert b"HUSTLER_BIND" not in output
