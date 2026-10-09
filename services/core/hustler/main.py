"""
Hustler FastAPI Sidecar — K-005
- Dinamik port (port=0, OS atar)
- UUID session token
- stdout: HUSTLER_BIND::PORT=xxxxx::TOKEN=yyyyy
- /health endpoint
- RFC 9457 Problem Details hata formatı
- SSE endpoint
- Bearer token doğrulama middleware
"""

import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services.core.hustler.db import Database
from services.core.hustler.api.routes.discovery import router as discovery_router
from services.core.hustler.storage.cache import YouTubeCache

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Session token — tek kaynak, sadece bu process'te yaşar
# ---------------------------------------------------------------------------
SESSION_TOKEN: str = secrets.token_urlsafe(32)


def _get_free_port() -> int:
    """OS'ten boş bir port al (port=0 trick)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


# ---------------------------------------------------------------------------
# Lifespan — açılışta port/token'ı stdout'a bas
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    port: int = app.state.bind_port
    app.state.session_token = SESSION_TOKEN
    
    # M2 Veri Katmanı Başlatma
    db_path = Path("hustler_core.db")
    db = Database(db_path)
    await db.init()
    
    cache = YouTubeCache(db, ttl_seconds=3600)
    await cache.init_tables()
    
    app.state.db = db
    app.state.cache = cache
    
    # Rust tarafı bu satırı okur
    print(f"HUSTLER_BIND::PORT={port}::TOKEN={SESSION_TOKEN}", flush=True)
    log.info("sidecar_started", port=port)
    yield
    await db.close()
    log.info("sidecar_stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Hustler Core", version="0.1.0", lifespan=lifespan)

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
        headers={"Content-Type": "application/problem+json"},
    )


app.add_exception_handler(HTTPException, _problem_details_handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Bearer token doğrulama yardımcısı
# ---------------------------------------------------------------------------
def _verify_token(request: Request) -> None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.removeprefix("Bearer ")
    # constant-time karşılaştırma
    if not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid token")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Sağlık yoklama — token gerektirmez."""
    return {"status": "ok"}


@app.get("/events")
async def sse_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events — Tauri Channel'e köprülenir."""
    _verify_token(request)

    async def _generate() -> AsyncIterator[str]:
        yield "data: connected\n\n"
        # Gerçek olaylar ilerleyen milestone'larda eklenir

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = _get_free_port()
    app.state.bind_port = port
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
