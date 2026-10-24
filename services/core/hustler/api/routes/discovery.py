from typing import Any, Optional
import os
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
import structlog
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.api.auth import verify_token
from services.core.hustler.db import Database
from services.core.hustler.discovery.canary import CanaryStatus, run_ytdlp_canary_async
from services.core.hustler.discovery.service import fallback_discovery, run_ytdlp_topic_discovery
from services.core.hustler.services.discovery import DiscoveryOrchestrator
from services.core.hustler.storage.channels import ChannelRepository

logger = structlog.get_logger()
# Yetkilendirme istek gövdesi doğrulamasından önce çalışır (anonim çağrıya 422 değil 401)
router = APIRouter(dependencies=[Depends(verify_token)])


class DiscoveryRunRequest(BaseModel):
    topic: str
    max_results: int = 50
    score_threshold: float = 30.0
    # Kanal-Merkezli Mimari (Faz 2/2): araştırma sonuçlarını kanala bağlar
    channel_id: Optional[str] = None


async def _enrich_with_db_results(
    db: Database, results: dict[str, Any], payload: DiscoveryRunRequest
) -> dict[str, Any]:
    """Orkestratör yanıtına discovery_videos tablosundaki kazananları ekler."""
    enriched = dict(results)
    if "results" not in enriched:
        try:
            conn = await db.get_reader()
            try:
                async with conn.execute(
                    "SELECT video_id, title, score FROM discovery_videos WHERE topic = ? ORDER BY score DESC LIMIT ?",
                    (payload.topic, payload.max_results),
                ) as cur:
                    rows = await cur.fetchall()
            finally:
                await conn.close()
            enriched["results"] = [
                {"video_id": r[0], "id": r[0], "title": r[1], "score": r[2], "topic": payload.topic}
                for r in rows
            ]
        except Exception:
            enriched["results"] = []
    enriched.setdefault("degraded", False)
    enriched.setdefault("warning", None)
    return enriched


async def _canary_requires_fallback() -> bool:
    """Asenkron yt-dlp kanaryası bozuk çıkarıcı tespit ederse True döner."""
    try:
        canary_rep = await run_ytdlp_canary_async(timeout_sec=2.0)
        if canary_rep.status in (
            CanaryStatus.DEGRADED_EXTRACTOR_BROKEN,
            CanaryStatus.SCHEMA_MISMATCH,
        ):
            logger.warning(
                "yt-dlp kanaryası bozuk çıkarıcı tespit etti, kırılmaz kurtarma hattına geçiliyor",
                status=canary_rep.status,
            )
            return True
    except Exception as exc:
        logger.warning("Kanarya kontrolü sırasında hata, devam ediliyor", error=str(exc))
    return False


async def _run_discovery_core(
    payload: DiscoveryRunRequest, db: Database, cache: Any, api_key: str
) -> Any:
    """K-205 & K-806 keşif çekirdeği: kanarya → YouTube orkestratörü → kurtarma hattı."""
    if await _canary_requires_fallback():
        return await fallback_discovery(db=db, topic=payload.topic)

    logger.info("API üzerinden Discovery tetiklendi", topic=payload.topic, threshold=payload.score_threshold)

    try:
        async with YouTubeClient(api_key=api_key, cache=cache) as youtube_client:
            orchestrator = DiscoveryOrchestrator(youtube_client, db)
            await orchestrator.init_tables()

            results = await orchestrator.run_discovery(
                topic=payload.topic,
                max_results=payload.max_results,
                score_threshold=payload.score_threshold,
            )
            if isinstance(results, dict):
                return await _enrich_with_db_results(db, results, payload)
            return results
    except Exception as exc:
        logger.warning(
            "Discovery hatası yakalandı, kırılmaz kurtarma hattı devreye giriyor",
            topic=payload.topic,
            error=str(exc),
        )
        return await fallback_discovery(db=db, topic=payload.topic)


async def _link_results_to_channel(db: Database, channel_id: str, topic: str, response: Any) -> Any:
    """Keşif sonuçlarını channel_id ile discovery_videos tablosuna bağlar ve yanıta ekler."""
    if not isinstance(response, dict):
        return response
    raw_items = response.get("results")
    items = [it for it in raw_items if isinstance(it, dict)] if isinstance(raw_items, list) else []
    try:
        linked = await ChannelRepository(db).record_research(channel_id, topic, items)
    except Exception as exc:
        logger.warning("Kanal araştırma bağı yazılamadı", channel_id=channel_id, error=str(exc))
        linked = 0
    linked_response = dict(response)
    linked_response["channel_id"] = channel_id
    linked_response["linked_to_channel"] = linked
    return linked_response


@router.post("/discovery/run")
async def run_discovery(payload: DiscoveryRunRequest, request: Request) -> Any:
    """
    K-205 & K-806: Kırılmaz Keşif (Resilient Discovery) Uç Noktası
    Önce asenkron yt-dlp kanaryasını test eder; çıkarıcı bozuksa veya YouTube API hata
    verirse sıfır-çöküş (Zero-Crash) prensibiyle yerel önbellek / şablon hattına geçer.
    channel_id verilirse sonuçlar ilgili kanala bağlanır (Kanal İçerik Araştırma Motoru).
    """
    db = getattr(request.app.state, "db", None)
    cache = getattr(request.app.state, "cache", None)

    if not db or not cache:
        raise HTTPException(status_code=500, detail="DB or Cache not initialized in app.state")

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key and not payload.channel_id:
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY ortam değişkeni eksik")

    if api_key:
        response = await _run_discovery_core(payload, db, cache, api_key)
    else:
        # YOUTUBE_API_KEY olmadığında yt-dlp üzerinden gerçek YouTube araması yapar;
        # çıkarıcı/ağ başarısız olursa kırılmaz kurtarma hattına (fallback_discovery) düşer.
        response = await run_ytdlp_topic_discovery(db=db, topic=payload.topic, max_results=payload.max_results)

    if payload.channel_id:
        return await _link_results_to_channel(db, payload.channel_id, payload.topic, response)
    return response
