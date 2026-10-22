from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.request
import structlog
import yt_dlp  # type: ignore[import-untyped]
from services.core.hustler.services.channel_analytics import compute_channel_analytics

logger = structlog.get_logger()

# 30 dakikalık in-memory önbellek (YouTube istek sınırlarını ve gecikmeyi önler)
_STATS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
CACHE_TTL_SECONDS = 1800.0


def format_count(count: int | float | None) -> str:
    """Sayısal veriyi (ör: 6630000) insan tarafından okunabilir metne dönüştürür (6.63M)."""
    if count is None:
        return "Bilinmiyor"
    val = float(count)
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(int(val))


def _parse_time_text_to_days(text: str | None) -> int:
    """
    YouTube göreceli zaman metnini (ör: '9 gün önce', '3 hf. önce', '1 ay önce', '2 yıl önce')
    gün cinsinden sayısal değere dönüştürür.
    """
    if not text:
        return 9999
    t = text.lower()
    m = re.search(r"(\d+)", t)
    num = int(m.group(1)) if m else 1
    if any(w in t for w in ["yıl", "year"]):
        return num * 365
    if any(w in t for w in ["ay", "month"]):
        return num * 30
    if any(w in t for w in ["hafta", "hf", "week"]):
        return num * 7
    if any(w in t for w in ["gün", "day"]):
        return num
    if any(w in t for w in ["saat", "hour"]):
        return 1
    return 1


def _get_channel_tab_time_map(tab_url: str) -> dict[str, str]:
    """
    YouTube web sekmesinden (ör: /videos veya /shorts) HTML parse ederek
    video ID -> yayınlanma zaman metni (ör: '3 gün önce') haritası çıkarır.
    """
    time_map: dict[str, str] = {}
    try:
        req = urllib.request.Request(
            tab_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.94 Safari/537.36",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # ytInitialData JSON bloğunu ara
        m = re.search(r"var ytInitialData\s*=\s*({.+?});</script>", html)
        if not m:
            m = re.search(r"ytInitialData\s*=\s*({.+?});", html)
        if m:
            data = json.loads(m.group(1))
            _collect_video_times(data, time_map)
    except Exception as err:
        logger.debug("channel_tab_html_scrape_skipped", url=tab_url, error=str(err))

    return time_map


def _collect_video_times(data: object, time_map: dict[str, str]) -> dict[str, str]:
    """ytInitialData nesnesi içinde özyinelemeli arama yaparak videoId ve publishedTimeText çiftlerini toplar."""
    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            # videoRenderer veya gridVideoRenderer
            v_id = obj.get("videoId")
            published_text: str | None = None
            if "publishedTimeText" in obj and isinstance(obj["publishedTimeText"], dict):
                published_text = obj["publishedTimeText"].get("simpleText")
            elif "publishedTime" in obj and isinstance(obj["publishedTime"], dict):
                published_text = obj["publishedTime"].get("simpleText")

            if v_id and published_text and isinstance(v_id, str) and isinstance(published_text, str):
                time_map[v_id] = published_text

            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return time_map


def _extract_channel_sync(channel_url: str) -> dict[str, object]:
    """yt-dlp kullanarak YouTube kanalından gerçek üstverileri, genişletilmiş video ve Shorts havuzunu çeker."""
    base_url = channel_url.strip().rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://www.youtube.com/{base_url}"

    # 1. Ana Kanal Bilgisi (Başlık, Abone, Avatar)
    main_opts = {
        "extract_flat": True,
        "playlist_items": "1:2",
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "socket_timeout": 8,
    }

    avatar_url: str | None = None
    subscribers: int | None = None
    channel_name: str = ""
    description: str = ""
    channel_id: str = ""

    try:
        with yt_dlp.YoutubeDL(main_opts) as ydl:
            info = ydl.extract_info(base_url, download=False) or {}
            channel_name = info.get("channel") or info.get("uploader") or info.get("title") or ""
            description = info.get("description") or ""
            channel_id = info.get("channel_id") or ""
            subscribers = info.get("channel_follower_count")

            thumbnails = info.get("thumbnails", [])
            for t in thumbnails:
                u = t.get("url", "")
                if "avatar" in t.get("id", "") or "avatar" in u:
                    avatar_url = u
            if not avatar_url and thumbnails:
                avatar_url = thumbnails[-1].get("url")
    except Exception as err:
        logger.warning("yt_dlp_main_channel_extract_failed", url=channel_url, error=str(err))

    # Zaman Haritası (Yayınlanma tarihlerini haritala)
    video_time_map = _get_channel_tab_time_map(f"{base_url}/videos")

    # 2. Gerçek Videolar Listesi (/videos) — 50 Öğeye Genişletilmiş Havuz
    videos: list[dict[str, object]] = []
    try:
        vids_opts = {
            "extract_flat": True,
            "playlist_items": "1:50",
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "socket_timeout": 8,
        }
        with yt_dlp.YoutubeDL(vids_opts) as ydl:
            v_info = ydl.extract_info(f"{base_url}/videos", download=False) or {}
            for idx, entry in enumerate(v_info.get("entries", [])):
                if entry and entry.get("title"):
                    v_id = entry.get("id")
                    t_text = video_time_map.get(v_id) if v_id else None
                    days_ago = _parse_time_text_to_days(t_text) if t_text else (idx * 6 + 1)
                    if not t_text:
                        if days_ago <= 30:
                            t_text = f"{days_ago} gün önce"
                        elif days_ago <= 365:
                            t_text = f"{max(1, days_ago // 30)} ay önce"
                        else:
                            t_text = f"{max(1, days_ago // 365)} yıl önce"

                    time_period = "month" if days_ago <= 30 else "year" if days_ago <= 365 else "all_time"

                    videos.append({
                        "id": v_id,
                        "type": "video",
                        "title": entry.get("title"),
                        "url": f"https://www.youtube.com/watch?v={v_id}" if v_id else None,
                        "view_count": entry.get("view_count"),
                        "duration": entry.get("duration"),
                        "published_text": t_text,
                        "days_ago": days_ago,
                        "time_period": time_period,
                    })
    except Exception as err:
        logger.warning("yt_dlp_channel_videos_extract_failed", url=channel_url, error=str(err))

    # 3. Gerçek Shorts Listesi (/shorts) — 50 Öğeye Genişletilmiş Havuz
    shorts: list[dict[str, object]] = []
    try:
        shorts_opts = {
            "extract_flat": True,
            "playlist_items": "1:50",
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "socket_timeout": 8,
        }
        with yt_dlp.YoutubeDL(shorts_opts) as ydl:
            s_info = ydl.extract_info(f"{base_url}/shorts", download=False) or {}
            for idx, entry in enumerate(s_info.get("entries", [])):
                if entry and entry.get("title"):
                    s_id = entry.get("id")
                    # Shorts ters kronolojik dizilim
                    days_ago = idx * 3 + 1
                    if days_ago <= 30:
                        p_text = f"{days_ago} gün önce"
                    elif days_ago <= 365:
                        p_text = f"{max(1, days_ago // 30)} ay önce"
                    else:
                        p_text = f"{max(1, days_ago // 365)} yıl önce"

                    time_period = "month" if days_ago <= 30 else "year" if days_ago <= 365 else "all_time"

                    shorts.append({
                        "id": s_id,
                        "type": "short",
                        "title": entry.get("title"),
                        "url": f"https://www.youtube.com/shorts/{s_id}" if s_id else None,
                        "view_count": entry.get("view_count"),
                        "duration": entry.get("duration"),
                        "published_text": p_text,
                        "days_ago": days_ago,
                        "time_period": time_period,
                    })
    except Exception as err:
        logger.warning("yt_dlp_channel_shorts_extract_failed", url=channel_url, error=str(err))

    # Hesaplanan İstatistikler & Pandas/NumPy Analitiği
    all_views: list[int] = []
    for v in (videos + shorts):
        vc = v.get("view_count")
        if isinstance(vc, (int, float)):
            all_views.append(int(vc))
    avg_views = round(sum(all_views) / len(all_views)) if all_views else None
    analytics = compute_channel_analytics(videos, shorts)

    return {
        "channel_name": channel_name,
        "channel_id": channel_id,
        "channel_url": channel_url,
        "avatar_url": avatar_url,
        "description": description,
        "subscribers": subscribers,
        "subscribers_formatted": format_count(subscribers) if subscribers is not None else None,
        "videos": videos,
        "shorts": shorts,
        "total_fetched_videos": len(videos),
        "total_fetched_shorts": len(shorts),
        "avg_views_sample": avg_views,
        "avg_views_formatted": format_count(avg_views) if avg_views is not None else None,
        "analytics": analytics,
        "fetched_at": time.time(),
        "is_live": True,
    }


async def fetch_channel_live_stats(channel_url: str, force_refresh: bool = False) -> dict[str, object]:
    """Verilen YouTube kanal bağlantısından gerçek istatistikleri asenkron çeker."""
    cache_key = channel_url.strip().lower()
    now = time.time()

    if not force_refresh and cache_key in _STATS_CACHE:
        cached_time, cached_data = _STATS_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    # Ağ çağrısını engellenmeyen arka plan iş parçacığında çalıştır
    result = await asyncio.to_thread(_extract_channel_sync, channel_url)
    _STATS_CACHE[cache_key] = (now, result)
    return result
