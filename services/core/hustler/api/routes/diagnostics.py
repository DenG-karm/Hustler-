"""
K-803: Tanılama Paketi API Rotası (/api/v1/diagnostics/export)
- Sistem sağlık raporu, sürümler, son loglar ve oturum meta özetini içeren
  hustler_diag_<timestamp>.zip dosyasını üretir ve dışa aktarır.
- Bearer token ile yetkilendirilir.
- Medya dosyaları (.mp4, .wav vb.) ve ham SQLite veritabanı kesinlikle dahil edilmez.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
import structlog

from services.core.hustler.api.auth import verify_token
from services.core.hustler.db.engine import Database
from services.core.hustler.diagnostics.bundler import async_create_diagnostics_bundle

logger = structlog.get_logger()
router = APIRouter(dependencies=[Depends(verify_token)])


@router.post("/diagnostics/export", response_model=None)
@router.get("/diagnostics/export", response_model=None)
async def export_diagnostics(
    request: Request,
    format: str = Query("zip", description="Dönüş formatı: 'zip' (dosya indirme) veya 'json' (dosya meta verisi)"),
) -> Response:
    """
    Sistemin anlık röntgenini çeken, PII ve sırları maskelenmiş tanılama .zip paketini üretir.
    """
    db = getattr(request.app.state, "db", None)
    if not isinstance(db, Database):
        raise HTTPException(status_code=500, detail="Database not initialized in app.state")

    output_dir = Path("runs/diagnostics")
    try:
        bundle_path = await async_create_diagnostics_bundle(output_dir, db)
    except Exception as e:
        logger.error("diagnostics_export_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Tanılama paketi üretilemedi: {e}") from e

    if format == "json":
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "filename": bundle_path.name,
                "bundle_path": str(bundle_path.resolve()),
                "size_bytes": bundle_path.stat().st_size,
            },
        )

    return FileResponse(
        path=bundle_path,
        media_type="application/zip",
        filename=bundle_path.name,
        headers={"X-Bundle-Path": str(bundle_path.resolve())},
    )
