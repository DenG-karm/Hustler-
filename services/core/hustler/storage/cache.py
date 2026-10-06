import time
import json
from typing import Optional

import structlog
from services.core.hustler.db import Database

logger = structlog.get_logger()

class YouTubeCache:
    def __init__(self, db: Database, ttl_seconds: int = 3600):
        self.db = db
        self.ttl_seconds = ttl_seconds
        
    async def init_tables(self):
        """Tabloyu oluşturur (Eğer yoksa). Yazma kuyruğu üzerinden geçer."""
        await self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS youtube_cache (
                cache_key TEXT PRIMARY KEY,
                response_json TEXT,
                created_at REAL
            )
        """)
        
    async def get(self, cache_key: str) -> Optional[dict]:
        """Süresi dolmamış (TTL) cache verisini getirir."""
        try:
            # ReaderPool üzerinden kilitsiz okuma (WAL)
            conn = await self.db.get_reader()
            async with conn.execute("SELECT response_json, created_at FROM youtube_cache WHERE cache_key = ?", (cache_key,)) as cursor:
                row = await cursor.fetchone()
                
            await conn.close()
            
            if row:
                response_json, created_at = row
                if time.time() - created_at <= self.ttl_seconds:
                    logger.debug("Cache Hit (Veritabanından)", cache_key=cache_key)
                    return json.loads(response_json)
                else:
                    logger.debug("Cache Expired (Süresi dolmuş)", cache_key=cache_key)
            else:
                logger.debug("Cache Miss", cache_key=cache_key)
            return None
        except Exception as e:
            logger.error("Cache get hatası", error=str(e))
            return None
            
    async def set(self, cache_key: str, data: dict) -> None:
        """Veriyi M0 WriterQueue üzerinden SQLite'a yazar. (Doğrudan INSERT yoktur, kuyruğa iş eklenir)"""
        data_json = json.dumps(data)
        created_at = time.time()
        
        # UPSERT
        query = """
            INSERT INTO youtube_cache (cache_key, response_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_json=excluded.response_json,
                created_at=excluded.created_at
        """
        await self.db.execute_write(query, (cache_key, data_json, created_at))
        logger.debug("Cache Set (Yazıcı Kuyruğuna Eklendi)", cache_key=cache_key)
