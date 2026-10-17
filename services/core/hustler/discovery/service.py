"""Hustler Kırılmaz Keşif Hattı Servisi (services/core/hustler/discovery/service.py).

K-806: yt-dlp bozulması durumunda sıfır-çöküş (Zero-Crash) kurtarma hattı.
Önce yerel SQLite youtube_cache tablosunu sorgular.
Önbellek boşsa deterministik fallback şablonu ile çalışmaya devam eder.
"""

from __future__ import annotations

import json
import structlog

from services.core.hustler.db import Database

logger = structlog.get_logger()

DEGRADED_WARNING_MSG: str = (
    "YouTube çıkarıcısı geçici olarak devre dışı. Sonuçlar yerel önbellek veya deterministik şablondan sağlandı."
)

FALLBACK_TEMPLATES: list[tuple[str, str, float]] = [
    ("{topic}: Kimsenin Bilmediği 3 Kritik Gerçek", "Bunu daha önce hiç duymadınız!", 92.5),
    ("{topic} Hakkında Büyük Yanılgı: Gerçekte Ne Oluyor?", "Gördüğünüz her şeye inanmayın.", 88.0),
    ("{topic} Geleceğimizi Nasıl Değiştirecek?", "2030 yılına kadar her şey değişecek.", 84.5),
    ("Neden Herkes {topic} Konuşuyor?", "İşte arkasındaki gizli mekanizma.", 79.0),
    ("{topic} ile Başarılı Olmanın 5 Altın Kuralı", "Uzmanların uyguladığı yöntemler.", 74.0),
]


def generate_deterministic_fallback(topic: str) -> list[dict[str, object]]:
    """Hiçbir ağ veya önbellek bulunamadığında deterministik video adayları üretir."""
    clean_topic = topic.strip().title() if topic else "Trend"
    topic_slug = clean_topic.lower().replace(" ", "_")
    seed = sum(ord(c) for c in clean_topic)

    results: list[dict[str, object]] = []
    for idx, (title_tpl, hook_tpl, score) in enumerate(FALLBACK_TEMPLATES):
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


def _parse_cached_video_item(item: dict[str, object], topic: str) -> dict[str, object] | None:
    """Tek bir önbellek öğesini ayrıştırır."""
    vid = item.get("id")
    if isinstance(vid, dict):
        vid = vid.get("videoId")
    if not (vid and isinstance(vid, str)):
        return None

    snippet = item.get("snippet", {})
    title = snippet.get("title", f"{topic} Videosu") if isinstance(snippet, dict) else f"{topic} Videosu"

    return {
        "video_id": vid,
        "id": vid,
        "title": str(title),
        "hook": f"{title} — Önbellekten kurtarılan analiz",
        "score": 88.0,
        "topic": topic,
        "view_count": 120000,
    }


def _extract_videos_from_response_json(resp_json: str, topic: str) -> list[dict[str, object]]:
    """Ham response_json string'inden geçerli video adaylarını çıkarır."""
    try:
        data = json.loads(str(resp_json))
        if not isinstance(data, dict):
            return []
        items = data.get("items", [])
        if not isinstance(items, list):
            return []

        parsed: list[dict[str, object]] = []
        for item in items:
            if isinstance(item, dict):
                v = _parse_cached_video_item(item, topic)
                if v:
                    parsed.append(v)
        return parsed
    except Exception:
        return []


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
            cached_videos.extend(_extract_videos_from_response_json(str(resp_json), topic))
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
