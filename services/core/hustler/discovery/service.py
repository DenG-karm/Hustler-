"""K-806 (Adım 2/3): Kırılmaz Keşif Hattı ve Kurtarma Servisi (services/core/hustler/discovery/service.py)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import hashlib
import json
from pathlib import Path
import re
import subprocess

import structlog

from services.core.hustler.db import Database
from services.core.hustler.discovery.canary import CanaryStatus, run_ytdlp_canary_async

logger = structlog.get_logger()

DEGRADED_WARNING_MSG: str = "yt-dlp çıkarıcısı yanıt vermiyor; yerel kurtarma modu aktif."

try:
    from yt_dlp.utils import DownloadError, ExtractorError  # type: ignore[import-untyped]
except Exception:
    class DownloadError(Exception):  # type: ignore[no-redef]
        """yt-dlp indirme hatası fallback sınıfı."""

    class ExtractorError(Exception):  # type: ignore[no-redef]
        """yt-dlp çıkarıcı hatası fallback sınıfı."""


def generate_deterministic_fallback(topic: str) -> list[dict[str, object]]:
    """Kullanıcının girdiği topic üzerinden deterministik yerel/fallback fikir ve kaynak şablonu üretir."""
    clean_topic = topic.strip()
    topic_slug = re.sub(r"[^\w]+", "_", clean_topic.lower()).strip("_") or "trend"
    seed = int(hashlib.sha256(clean_topic.lower().encode("utf-8")).hexdigest()[:8], 16)

    templates = [
        ("{topic}: Kimsenin Bilmediği 3 Kritik Gerçek", "{topic} hakkında bildiğiniz her şeyi unutun! Perde arkası aralanıyor.", 96.0),
        ("{topic} ile 24 Saatte Sonuç Alma Rehberi", "Eğer {topic} konusunda başarılı olmak istiyorsanız, bu 3 kuralı uygulayın.", 91.0),
        ("2026'da {topic}: En Büyük Fırsatlar ve Hatalar", "Birçok insan {topic} yaparken bu ölümcül hataya düşüyor. Sakın yapmayın!", 87.0),
        ("{topic} Dünyasında Yapay Zeka Devrimi", "Gelecek burada: {topic} sektörü tamamen değişiyor, hazırlıklı mısınız?", 84.0),
        ("Sıfırdan İleri Seviyeye {topic} Stratejisi", "Adım adım {topic} rehberiyle dakikalar içinde seviye atlayın.", 80.0),
    ]

    results: list[dict[str, object]] = []
    for idx, (title_tpl, hook_tpl, base_score) in enumerate(templates):
        variation = float((seed + idx * 7) % 5)
        score = round(max(50.0, base_score - variation), 1)
        results.append({
            "video_id": f"fallback_{topic_slug}_{idx + 1}",
            "id": f"fallback_{topic_slug}_{idx + 1}",
            "title": title_tpl.format(topic=clean_topic),
            "hook": hook_tpl.format(topic=clean_topic),
            "score": score,
            "topic": clean_topic,
            "view_count": 150000 + (seed % 100000) - idx * 15000,
        })
    return results


def escape_like(s: str) -> str:
    """SQLite LIKE sorguları için \\, % ve _ karakterlerini ters bölü (\\) ile kaçırır."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def query_youtube_cache_for_topic(db: Database, topic: str) -> list[dict[str, object]]:
    """Yerel SQLite önbelleğinde (youtube_cache) topic ile eşleşen kayıtları arar."""
    try:
        conn = await db.get_reader()
        try:
            clean_raw = topic.strip().lower()
            clean = escape_like(clean_raw)
            words = [escape_like(w) for w in clean_raw.split()]
            variants = [f"%{clean}%", f"%{'+'.join(words)}%", f"%{r'\%20'.join(words)}%"]
            conds = " OR ".join(["LOWER(cache_key) LIKE ? ESCAPE '\\'" for _ in variants])
            async with conn.execute(
                f"SELECT response_json FROM youtube_cache WHERE {conds} ORDER BY created_at DESC LIMIT 5",
                tuple(variants),
            ) as cursor:
                rows = await cursor.fetchall()
        finally:
            await conn.close()

        cached_videos: list[dict[str, object]] = []
        for (resp_json,) in rows:
            try:
                data = json.loads(str(resp_json))
                if isinstance(data, dict):
                    items = data.get("items", [])
                    if isinstance(items, list):
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            vid = item.get("id")
                            if isinstance(vid, dict):
                                vid = vid.get("videoId")
                            snippet = item.get("snippet", {})
                            title = snippet.get("title", f"{topic} Videosu") if isinstance(snippet, dict) else f"{topic} Videosu"
                            if vid and isinstance(vid, str):
                                cached_videos.append({
                                    "video_id": vid,
                                    "id": vid,
                                    "title": str(title),
                                    "hook": f"{title} — Önbellekten kurtarılan analiz",
                                    "score": 88.0,
                                    "topic": topic,
                                    "view_count": 120000,
                                })
            except Exception:
                continue
        return cached_videos
    except Exception as exc:
        logger.warning("youtube_cache sorgulanırken hata oluştu", error=str(exc))
        return []


async def fallback_discovery(db: Database, topic: str) -> dict[str, object]:
    """yt-dlp bozulduğunda önce youtube_cache'e, yoksa deterministik şablona başvuran kurtarma fonksiyonu."""
    cached = await query_youtube_cache_for_topic(db, topic)
    items = cached if cached else generate_deterministic_fallback(topic)
    max_score = 0.0
    for it in items:
        sc = it.get("score")
        if isinstance(sc, (int, float)) and float(sc) > max_score:
            max_score = float(sc)

    logger.warning(
        "Kırılmaz Keşif Hattı Devrede (Graceful Degradation)",
        topic=topic,
        source="youtube_cache" if cached else "deterministic_template",
        item_count=len(items),
    )

    return {
        "results": items,
        "fetched": len(items),
        "discarded": 0,
        "inserted": 0,
        "max_score": max_score,
        "degraded": True,
        "warning": DEGRADED_WARNING_MSG,
    }


class ResilientDiscoveryService:
    """K-806: yt-dlp bozulmalarına karşı dayanıklı (Zero-Crash) keşif servisi."""

    def __init__(self, db: Database, binary_path: Path | str | None = None) -> None:
        self.db = db
        self.binary_path = binary_path

    async def run_resilient_discovery(
        self,
        topic: str,
        orchestrator_call: Callable[[], Awaitable[dict[str, object]]] | None = None,
    ) -> dict[str, object]:
        """yt-dlp / API çağrısını yürütür, hata durumunda yerel önbellek ve deterministik şablonla döner."""
        try:
            # Kanarya kontrolü: Çıkarıcı sağlığını hızlıca sına
            canary_rep = await run_ytdlp_canary_async(timeout_sec=2.0, binary_path=self.binary_path)
            if canary_rep.status in (
                CanaryStatus.DEGRADED_EXTRACTOR_BROKEN,
                CanaryStatus.SCHEMA_MISMATCH,
            ):
                logger.warning("yt-dlp kanaryası bozuk çıkarıcı tespit etti", status=canary_rep.status)
                return await fallback_discovery(self.db, topic)

            if orchestrator_call is not None:
                res = await orchestrator_call()
                if isinstance(res, dict):
                    if "degraded" not in res:
                        res["degraded"] = False
                    if "warning" not in res:
                        res["warning"] = None
                    return res

            return await fallback_discovery(self.db, topic)
        except (
            ExtractorError,
            DownloadError,
            subprocess.SubprocessError,
            TimeoutError,
            Exception,
        ) as exc:
            logger.warning("Keşif hattında hata yakalandı, kurtarma moduna geçiliyor", error=str(exc))
            return await fallback_discovery(self.db, topic)
