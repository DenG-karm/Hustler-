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
from services.core.hustler.api.routes.jobs import router as jobs_router
from services.core.hustler.api.routes.pipeline import router as pipeline_router
from services.core.hustler.api.routes.diagnostics import router as diagnostics_router
from services.core.hustler.storage.cache import YouTubeCache
from services.core.hustler.storage.jobs import JobRepository
from services.core.hustler.storage.scripts import ScriptRepository
from services.core.hustler.storage.sessions import ProjectSessionRepository
from services.core.hustler.infrastructure.event_broker import EventBroker

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
    app.state.event_broker = EventBroker()
    app.state.running_jobs = {}
    
    # M2 Veri Katmanı Başlatma
    db_path = Path("hustler_core.db")
    db = Database(db_path)
    await db.init()
    
    cache = YouTubeCache(db, ttl_seconds=3600)
    await cache.init_tables()
    
    job_repo = JobRepository(db)
    await job_repo.init_table()
    await job_repo.reap_zombies()

    script_repo = ScriptRepository(db)
    await script_repo.init_table()
    
    session_repo = ProjectSessionRepository(db)
    await session_repo.init_table()
    recovered_count = await session_repo.recover_interrupted_sessions()
    if recovered_count > 0:
        log.warn("sessions_recovered_on_startup", count=recovered_count)

    app.state.db = db
    app.state.cache = cache
    app.state.job_repo = job_repo
    app.state.script_repo = script_repo
    app.state.session_repo = session_repo

    log.info("sidecar_started")  # token ve port burada bilinçli olarak yok
    yield
    # Kapanışta çalışan işleri iptal et
    running_jobs = getattr(app.state, "running_jobs", {})
    if isinstance(running_jobs, dict):
        for t in running_jobs.values():
            if hasattr(t, "done") and not t.done() and hasattr(t, "cancel"):
                t.cancel()
    await db.close()
    log.info("sidecar_stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Hustler Core", version="0.1.0", lifespan=lifespan)
app.state.session_token = SESSION_TOKEN

app.include_router(discovery_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(diagnostics_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# RFC 7807 / RFC 9457 Problem Details hata işleyicileri
# ---------------------------------------------------------------------------
async def _problem_details_handler(request: Request, exc: HTTPException) -> JSONResponse:
    title = str(exc.detail) if isinstance(exc.detail, str) else "HTTP Hatası"
    code = getattr(exc, "code", f"ERR_{exc.status_code}")
    content = {
        "type": f"https://hustler.local/errors/{exc.status_code}",
        "title": title,
        "status": exc.status_code,
        "detail": str(exc.detail),
        "instance": str(request.url.path),
        "code": code,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={**(exc.headers or {}), "Content-Type": "application/problem+json"},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_server_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "type": "https://hustler.local/errors/500",
            "title": "Sunucu İşlem Hatası",
            "status": 500,
            "detail": "Sunucu tarafında beklenmeyen bir hata oluştu. Güvenlik nedeniyle teknik detaylar gizlendi.",
            "instance": str(request.url.path),
            "code": "INTERNAL_SERVER_ERROR",
        },
        headers={"Content-Type": "application/problem+json"},
    )


app.add_exception_handler(HTTPException, _problem_details_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, _unhandled_exception_handler)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Sağlık yoklama — token gerektirmez."""
    return {"status": "ok"}


@app.get("/events", dependencies=[Depends(verify_token)])
async def sse_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events — Tauri Event köprüsüne yayınlanır."""
    broker: EventBroker | None = getattr(request.app.state, "event_broker", None)
    if broker is None:
        async def _single_event() -> AsyncIterator[str]:
            yield "data: connected\n\n"

        return StreamingResponse(_single_event(), media_type="text/event-stream")

    return StreamingResponse(
        broker.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
