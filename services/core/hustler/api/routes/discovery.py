from typing import Any
import os
import secrets
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import structlog
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.services.discovery import DiscoveryOrchestrator

logger = structlog.get_logger()
router = APIRouter()

class DiscoveryRunRequest(BaseModel):
    topic: str
    max_results: int = 50
    score_threshold: float = 30.0

def verify_token(request: Request) -> Any:
    """Gelen isteğin Bearer token'ını doğrular (Tauri köprüsü)"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth.removeprefix("Bearer ")
    
    session_token = getattr(request.app.state, "session_token", "")
    if not secrets.compare_digest(token, session_token):
        raise HTTPException(status_code=403, detail="Invalid token")

@router.post("/discovery/run")
async def run_discovery(payload: DiscoveryRunRequest, request: Request) -> Any:
    """
    K-205: Discovery Orchestrator Tetikleyicisi
    Belirtilen anahtar kelime için Shorts videolarını tarar, puanlar ve eşiği geçenleri veritabanına yazar.
    """
    verify_token(request)
    
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
