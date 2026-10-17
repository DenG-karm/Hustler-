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

import asyncio
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
from services.core.hustler.api.routes.pipeline import (
    router as pipeline_router,
    alias_router as pipeline_alias_router,
)
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
    
    # M2 Veri Katmanı Başlatma (Tauri src-tauri altından başlatıldığında kök dizine sabitle)
    env_db_path = os.environ.get("HUSTLER_DB_PATH")
    cwd = Path.cwd()
    if env_db_path:
        db_path = Path(env_db_path).resolve()
    elif cwd.name == "src-tauri":
        db_path = Path(__file__).resolve().parents[3] / "hustler_core.db"
    else:
        db_path = (cwd / "hustler_core.db").resolve()
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

    from services.core.hustler.tasks.scheduler import maintenance_loop
    maint_task = asyncio.create_task(
        maintenance_loop(db=db, cache_ttl_sec=3600, interval_sec=1800)
    )
    app.state.maintenance_task = maint_task

    log.info("sidecar_started")  # token ve port burada bilinçli olarak yok
    yield
    # Kapanışta arka plan bakım görevini ve çalışan işleri iptal et
    if maint_task and not maint_task.done():
        maint_task.cancel()
        try:
            await maint_task
        except asyncio.CancelledError:
            pass

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
app = FastAPI(title="Hustler Core", version="1.0.0", lifespan=lifespan)
app.state.session_token = SESSION_TOKEN

app.include_router(discovery_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(pipeline_alias_router, prefix="/api/v1")
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


@app.post("/api/v1/system/shutdown", dependencies=[Depends(verify_token)])
async def shutdown(request: Request) -> dict[str, str]:
    """
    K-807: Kontrollü ve Temiz Kapanış (Graceful Shutdown) Uç Noktası.
    - Yalnızca geçerli HUSTLER_SESSION_TOKEN ile tetiklenebilir.
    - DB üzerinde PRAGMA wal_checkpoint(TRUNCATE) çalıştırır ve veritabanını kapatır.
    - Uvicorn sunucusuna çıkış sinyali verir (server.should_exit = True).
    """
    log.info("graceful_shutdown_requested")
    db = getattr(request.app.state, "db", None)
    if db and hasattr(db, "checkpoint_truncate"):
        try:
            await db.checkpoint_truncate()
        except Exception as e:
            log.warning("shutdown_wal_checkpoint_failed", error=str(e))

    server = getattr(request.app.state, "server", None)

    async def _trigger_exit() -> None:
        await asyncio.sleep(0.15)
        if server:
            server.should_exit = True
        else:
            import signal
            import sys
            if sys.platform != "win32":
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                loop = asyncio.get_running_loop()
                loop.stop()

    asyncio.create_task(_trigger_exit())
    return {"status": "shutting_down"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = _resolve_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    app.state.server = server
    server.run()

