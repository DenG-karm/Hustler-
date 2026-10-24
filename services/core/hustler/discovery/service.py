"""Hustler Kırılmaz Keşif Hattı Servisi (services/core/hustler/discovery/service.py).

K-806: yt-dlp bozulması durumunda sıfır-çöküş (Zero-Crash) kurtarma hattı.
Önce yerel SQLite youtube_cache tablosunu sorgular.
Önbellek boşsa deterministik fallback şablonu ile çalışmaya devam eder.
"""

from __future__ import annotations

import asyncio
import json
import math
import structlog
import yt_dlp  # type: ignore[import-untyped]

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


def _format_duration_sec(dur: int | float | None) -> tuple[str, str]:
    if not isinstance(dur, (int, float)) or dur <= 0:
        return "0:45", "short"
    sec = int(dur)
    fmt = "short" if sec <= 65 else "video"
    return f"{sec // 60}:{sec % 60:02d}", fmt


def _score_from_views(views: int) -> float:
    if views <= 0:
        return 60.0
    raw = 50.0 + math.log10(max(1, views)) * 7.2
    return round(min(99.0, max(55.0, raw)), 1)


def _search_youtube_ytdlp_sync(topic: str, max_results: int = 12) -> list[dict[str, object]]:
    """yt-dlp ytsearch kullanarak konuyla ilgili gerçek YouTube videolarını ve üstverilerini çeker."""
    clean_topic = topic.strip()
    if not clean_topic:
        return []
    limit = max(1, min(25, max_results))
    opts = {
        "extract_flat": True,
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "socket_timeout": 8,
    }
    items: list[dict[str, object]] = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{clean_topic}", download=False) or {}
            for entry in info.get("entries", []) or []:
                if not isinstance(entry, dict):
                    continue
                vid = entry.get("id")
                title = entry.get("title")
                if not (isinstance(vid, str) and vid and isinstance(title, str) and title):
                    continue
                vc_raw = entry.get("view_count")
                views = int(vc_raw) if isinstance(vc_raw, (int, float)) else 0
                dur_raw = entry.get("duration")
                dur_sec = int(dur_raw) if isinstance(dur_raw, (int, float)) else 0
                dur_text, v_format = _format_duration_sec(dur_sec)
                channel_name = str(entry.get("channel") or entry.get("uploader") or "YouTube")
                url_prefix = "shorts/" if v_format == "short" else "watch?v="
                score = _score_from_views(views)
                items.append({
                    "video_id": vid,
                    "id": vid,
                    "title": title,
                    "hook": f"{channel_name} • {dur_text} ({'Shorts 9:16' if v_format == 'short' else 'Video 16:9'})",
                    "score": score,
                    "topic": clean_topic,
                    "view_count": views,
                    "duration": dur_sec,
                    "duration_text": dur_text,
                    "format": v_format,
                    "channel_name": channel_name,
                    "url": f"https://www.youtube.com/{url_prefix}{vid}",
                })
    except Exception as exc:
        logger.warning("ytdlp_live_search_failed", topic=clean_topic, error=str(exc))
    items.sort(key=lambda x: int(str(x.get("view_count") or 0)), reverse=True)
    return items


async def run_ytdlp_topic_discovery(db: Database, topic: str, max_results: int = 12) -> dict[str, object]:
    """Gerçek yt-dlp YouTube araması çalıştırır; yalnızca ağ/çıkarıcı tamamen başarısızsa fallback_discovery'ye geçer."""
    live_items = await asyncio.to_thread(_search_youtube_ytdlp_sync, topic, max_results)
    if not live_items:
        return await fallback_discovery(db=db, topic=topic)
    max_sc = max((float(str(it.get("score") or 0.0)) for it in live_items), default=0.0)
    return {
        "results": live_items,
        "fetched": len(live_items),
        "discarded": 0,
        "inserted": len(live_items),
        "max_score": max_sc,
        "degraded": False,
        "warning": None,
    }


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
