from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field

from services.core.hustler.api.auth import verify_token
from services.core.hustler.db import Database
from services.core.hustler.storage.channels import Channel, ChannelRepository
from services.core.hustler.services.channel_stats import fetch_channel_live_stats

router = APIRouter(dependencies=[Depends(verify_token)])


def _default_metrics() -> dict[str, int | float]:
    return {"total_scripts": 0, "total_research": 0, "avg_viral_score": 0.0}


@dataclass
class ChannelCreateRequest:
    name: Annotated[str, Field(min_length=2, description="Kanal adı (en az 2 karakter)")]
    channel_url: Annotated[str, Field(min_length=1, description="Kanal URL adresi")]
    description: str = ""


@dataclass
class ChannelResponse:
    id: str
    name: str
    channel_url: str
    description: str
    created_at: float
    metrics: dict[str, int | float] = field(default_factory=_default_metrics)


def _repo(request: Request) -> ChannelRepository:
    repo = getattr(request.app.state, "channel_repo", None)
    if isinstance(repo, ChannelRepository):
        return repo
    db = getattr(request.app.state, "db", None)
    if not isinstance(db, Database):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Veritabanı başlatılmamış (DB not initialized in app.state)",
        )
    return ChannelRepository(db)


def _to_response(
    channel: Channel, metrics: dict[str, int | float]
) -> ChannelResponse:
    """Kanalı ve hesaplanmış gerçek metriklerini ChannelResponse nesnesine dönüştürür."""
    merged = _default_metrics()
    merged.update(metrics)
    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        channel_url=channel.channel_url,
        description=channel.description,
        created_at=channel.created_at,
        metrics=merged,
    )


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(request: Request) -> list[ChannelResponse]:
    """Tüm kayıtlı kanalları ve özet metriklerini listeler."""
    repo = _repo(request)
    pairs = await repo.list_all_with_metrics()
    return [_to_response(channel, metrics) for channel, metrics in pairs]


@router.post(
    "/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    payload: ChannelCreateRequest, request: Request
) -> ChannelResponse:
    """Yeni bir kanal kaydı oluşturur."""
    repo = _repo(request)
    channel = await repo.create(
        name=payload.name.strip(),
        channel_url=payload.channel_url.strip(),
        description=payload.description.strip(),
    )
    metrics = await repo.get_metrics(channel.id)
    return _to_response(channel, metrics)


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel_detail(
    channel_id: str, request: Request
) -> ChannelResponse:
    """Kanal detayını ve analiz özetini getirir."""
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kanal bulunamadı: {channel_id}",
        )
    metrics = await repo.get_metrics(channel.id)
    return _to_response(channel, metrics)


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: str, request: Request
) -> dict[str, str]:
    """Belirtilen kanalı siler."""
    deleted = await _repo(request).delete(channel_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Silinecek kanal bulunamadı: {channel_id}",
        )
    return {"status": "deleted", "channel_id": channel_id}


@router.get("/channels/{channel_id}/live-stats")
async def get_channel_live_stats(
    channel_id: str, request: Request, refresh: bool = False
) -> dict[str, object]:
    """Kanalın gerçek YouTube abone, video, Shorts ve canlı istatistiklerini getirir."""
    repo = _repo(request)
    channel = await repo.get_by_id(channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kanal bulunamadı: {channel_id}",
        )
    live_data = await fetch_channel_live_stats(channel.channel_url, force_refresh=refresh)
    sqlite_metrics = await repo.get_metrics(channel.id)

    return {
        "channel_id": channel.id,
        "channel_name": channel.name,
        "channel_url": channel.channel_url,
        "description": channel.description,
        "ai_summary": getattr(channel, "ai_summary", ""),
        "created_at": channel.created_at,
        "live_data": live_data,
        "sqlite_metrics": sqlite_metrics,
    }

