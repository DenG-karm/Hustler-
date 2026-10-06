import structlog
import time
from services.core.hustler.adapters.youtube import YouTubeClient
from services.core.hustler.db import Database
from services.core.hustler.domain.scoring import calculate_score

logger = structlog.get_logger()

class DiscoveryOrchestrator:
    def __init__(self, youtube_client: YouTubeClient, db: Database):
        self.youtube = youtube_client
        self.db = db
        
    async def init_tables(self):
        """K-205 kapsamında kazanan videoları saklayacağımız veritabanı tablosu"""
        await self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS discovery_videos (
                video_id TEXT PRIMARY KEY,
                title TEXT,
                topic TEXT,
                score REAL,
                discovered_at REAL
            )
        """)

    async def run_discovery(self, topic: str, max_results: int = 50, score_threshold: float = 30.0) -> dict:
        """
        1. API/Cache üzerinden Shorts'ları çeker.
        2. Saf skorlama fonksiyonu üzerinden geçirir.
        3. Threshold altındakileri RAM'de çöpe atar.
        4. Kazananları (threshold'u geçenler) asenkron WriterQueue üzerinden diske yazar.
        """
        logger.info("Discovery süreci başlatıldı", topic=topic, threshold=score_threshold)
        
        # 1. Arama (Search)
        search_results = [item async for item in self.youtube.search_shorts(topic, max_results)]
        video_ids = [item["id"]["videoId"] for item in search_results if "videoId" in item["id"]]
        
        if not video_ids:
            logger.warning("Keşfedilecek video bulunamadı", topic=topic)
            return {"fetched": 0, "discarded": 0, "inserted": 0, "max_score": 0.0}
            
        # 2. Detaylı İstatistiklerin Çekilmesi
        details = await self.youtube.get_videos_details(video_ids)
        
        # 3. Skorlama ve Filtreleme İşlemi (RAM-Level)
        fetched = len(details)
        discarded = 0
        inserted = 0
        max_score = 0.0
        
        winning_videos = []
        
        for item in details:
            vid = item["id"]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            
            pub_at = snippet.get("publishedAt", "")
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            
            # Saf Domain Katmanı Çağrısı (Yan etkisiz skorlama)
            score = calculate_score(pub_at, views, likes, comments)
            
            if score > max_score:
                max_score = score
                
            if score < score_threshold:
                # Eşiğin altında kalanlar RAM'de çöpe atılır
                discarded += 1
            else:
                # Kazananlar
                winning_videos.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "topic": topic,
                    "score": score
                })
                inserted += 1
                
        # 4. Kazananların DB'ye Kaydı (Side-Effect: WriterQueue Üzerinden)
        now_ts = time.time()
        for v in winning_videos:
            await self.db.execute_write("""
                INSERT INTO discovery_videos (video_id, title, topic, score, discovered_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    score=excluded.score,
                    discovered_at=excluded.discovered_at
            """, (v["video_id"], v["title"], v["topic"], v["score"], now_ts))
            
        return {
            "fetched": fetched,
            "discarded": discarded,
            "inserted": inserted,
            "max_score": max_score
        }
