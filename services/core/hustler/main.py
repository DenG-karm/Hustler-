"""
Hustler FastAPI Sidecar — K-005
- Dinamik port (port=0, OS atar)
- Session token: Rust üretir, HUSTLER_SESSION_TOKEN ortam değişkeniyle iletir
  (stdout/argv/log'a ASLA yazılmaz); yoksa rastgele üretilir ve kimse bağlanamaz
- Port: HUSTLER_PORT (yoksa OS atar); Rust /health ile hazır olmayı yoklar
- /health endpoint
- RFC 9457 Problem Details hata formatı
- SSE endpoint
- Bearer token doğrulama middleware
"""

import os
import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services.core.hustler.api.auth import verify_token
from services.core.hustler.db import Database
from services.core.hustler.api.routes.discovery import router as discovery_router
from services.core.hustler.storage.cache import YouTubeCache

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Session token — tek kaynak, sadece bu process'te yaşar
# ---------------------------------------------------------------------------
TOKEN_ENV_VAR = "HUSTLER_SESSION_TOKEN"
PORT_ENV_VAR = "HUSTLER_PORT"


def _load_session_token() -> str:
    """Token'ı ortamdan alır ve ortamdan siler (ffmpeg gibi çocuklar miras almasın)."""
    token = os.environ.pop(TOKEN_ENV_VAR, "")
    return token or secrets.token_urlsafe(32)


SESSION_TOKEN: str = _load_session_token()


def _get_free_port() -> int:
    """OS'ten boş bir port al (port=0 trick)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


def _resolve_port() -> int:
    raw = os.environ.get(PORT_ENV_VAR)
    if raw is None:
        return _get_free_port()
    port = int(raw)
    if not 1024 <= port <= 65535:
        raise ValueError(f"{PORT_ENV_VAR} out of range: {port}")
    return port


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.session_token = SESSION_TOKEN
    
    # M2 Veri Katmanı Başlatma
    db_path = Path("hustler_core.db")
    db = Database(db_path)
    await db.init()
    
    cache = YouTubeCache(db, ttl_seconds=3600)
    await cache.init_tables()
    
    app.state.db = db
    app.state.cache = cache
    
    log.info("sidecar_started")  # token ve port burada bilinçli olarak yok
    yield
    await db.close()
    log.info("sidecar_stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Hustler Core", version="0.1.0", lifespan=lifespan)
app.state.session_token = SESSION_TOKEN

app.include_router(discovery_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# RFC 9457 Problem Details hata işleyici
# ---------------------------------------------------------------------------
async def _problem_details_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"https://hustler.local/errors/{exc.status_code}",
            "title": exc.detail,
            "status": exc.status_code,
            "instance": str(request.url.path),
        },
        # exc.headers (WWW-Authenticate vb.) düşmemeli
        headers={**(exc.headers or {}), "Content-Type": "application/problem+json"},
    )


app.add_exception_handler(HTTPException, _problem_details_handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Sağlık yoklama — token gerektirmez."""
    return {"status": "ok"}


@app.get("/events", dependencies=[Depends(verify_token)])
async def sse_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events — Tauri Channel'e köprülenir."""
    async def _generate() -> AsyncIterator[str]:
        yield "data: connected\n\n"
        # Gerçek olaylar ilerleyen milestone'larda eklenir

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = _resolve_port()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
