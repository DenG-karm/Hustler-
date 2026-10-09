from typing import Any
import os
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
import structlog
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.api.auth import verify_token
from services.core.hustler.services.discovery import DiscoveryOrchestrator

logger = structlog.get_logger()
# Yetkilendirme istek gövdesi doğrulamasından önce çalışır (anonim çağrıya 422 değil 401)
router = APIRouter(dependencies=[Depends(verify_token)])

class DiscoveryRunRequest(BaseModel):
    topic: str
    max_results: int = 50
    score_threshold: float = 30.0

@router.post("/discovery/run")
async def run_discovery(payload: DiscoveryRunRequest, request: Request) -> Any:
    """
    K-205: Discovery Orchestrator Tetikleyicisi
    Belirtilen anahtar kelime için Shorts videolarını tarar, puanlar ve eşiği geçenleri veritabanına yazar.
    """
    db = getattr(request.app.state, "db", None)
    cache = getattr(request.app.state, "cache", None)
    
    if not db or not cache:
        raise HTTPException(status_code=500, detail="DB or Cache not initialized in app.state")
        
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY ortam değişkeni eksik")
        
    logger.info("API üzerinden Discovery tetiklendi", topic=payload.topic, threshold=payload.score_threshold)
    
    # Asenkron Context Manager ile Client başlatıyoruz
    async with YouTubeClient(api_key=api_key, cache=cache) as youtube_client:
        orchestrator = DiscoveryOrchestrator(youtube_client, db)
        await orchestrator.init_tables()
        
        results = await orchestrator.run_discovery(
            topic=payload.topic, 
            max_results=payload.max_results, 
            score_threshold=payload.score_threshold
        )
        
        return results
