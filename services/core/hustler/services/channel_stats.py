from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.request
from collections import Counter
import structlog
import yt_dlp  # type: ignore[import-untyped]
from services.core.hustler.discovery.service import _search_youtube_ytdlp_sync
from services.core.hustler.services.channel_analytics import compute_channel_analytics

logger = structlog.get_logger()

_STOPWORDS: set[str] = {
    "ve", "ile", "bir", "bu", "da", "de", "için", "nasıl", "neden", "ne", "olan",
    "daha", "çok", "en", "mi", "mı", "mu", "mü", "gibi", "kadar", "sonra", "önce",
    "ama", "fakat", "veya", "ya", "ki", "her", "hiç", "var", "yok", "shorts", "short",
    "video", "youtube", "official", "resmi", "kanal", "kanalı", "the", "and", "for",
    "with", "that", "this", "from", "what", "how", "why", "who", "are", "was", "were",
}


def infer_channel_niche_query(
    channel_name: str,
    description: str,
    videos: list[dict[str, object]],
    shorts: list[dict[str, object]],
) -> str:
    """Kanalın gerçek video/Shorts başlıklarından ve açıklamasından gerçek niş arama sorgusunu çıkarır."""
    combined = sorted(
        videos + shorts,
        key=lambda x: int(str(x.get("view_count") or 0)),
        reverse=True,
    )
    corpus: list[str] = []
    for item in combined[:15]:
        t = str(item.get("title") or "").strip()
        if t:
            corpus.append(t)
    if description:
        corpus.append(description[:200])
    if channel_name:
        corpus.append(channel_name)

    words: list[str] = []
    for text in corpus:
        for token in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{3,}", text.lower()):
            if token not in _STOPWORDS and not token.isdigit():
                words.append(token)

    if not words:
        return (channel_name or description or "popüler bilim").strip()[:50]

    top_terms = [w for w, _ in Counter(words).most_common(4)]
    return " ".join(top_terms)

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


def _parse_int_from_text(text: str | None) -> int | None:
    """Metin içerisindeki toplam video veya görüntülenme sayısını ayrıştırır (ör: '1,234 video', '2.4B video', '45.2M görüntüleme')."""
    if not text:
        return None
    t = text.strip().lower()
    m_unit = re.search(r"([\d.,]+)\s*(mr|milyar|b|mn|milyon|m|b|bin|k)\b", t)
    if m_unit:
        raw_num = m_unit.group(1).replace(",", ".")
        unit = m_unit.group(2)
        try:
            val = float(raw_num)
            if unit in ("mr", "milyar", "b") and "bin" not in t:
                return int(val * 1_000_000_000)
            if unit in ("mn", "milyon", "m"):
                return int(val * 1_000_000)
            return int(val * 1_000)
        except ValueError:
            pass
    digits = re.sub(r"[^\d]", "", t)
    return int(digits) if digits else None


def _extract_totals_from_obj(obj: dict[str, object], totals: dict[str, int | None]) -> None:
    for k, v in obj.items():
        if k in ("videoCountText", "videosCountText") and isinstance(v, (str, dict)):
            txt = v if isinstance(v, str) else str(v.get("simpleText") or "")
            parsed = _parse_int_from_text(txt)
            if parsed is not None:
                totals["total_videos"] = parsed
        elif k == "viewCountText" and isinstance(v, (str, dict)) and "videoId" not in obj:
            txt = v if isinstance(v, str) else str(v.get("simpleText") or "")
            parsed = _parse_int_from_text(txt)
            if parsed is not None and parsed > (totals["total_views"] or 0):
                totals["total_views"] = parsed
        elif k == "content" and isinstance(v, str) and len(v) < 40 and any(c.isdigit() for c in v):
            low = v.lower()
            if "video" in low and totals["total_videos"] is None:
                totals["total_videos"] = _parse_int_from_text(v)
            elif "görüntüleme" in low or "views" in low:
                parsed = _parse_int_from_text(v)
                if parsed is not None and parsed > (totals["total_views"] or 0):
                    totals["total_views"] = parsed


def _extract_channel_totals_from_initial_data(data: object) -> dict[str, int | None]:
    """ytInitialData ağacından kanalın gerçek toplam video sayısını ve tüm zamanlar izlenmesini çıkarır."""
    totals: dict[str, int | None] = {"total_videos": None, "total_views": None}

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            _extract_totals_from_obj(obj, totals)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return totals


def _get_channel_tab_time_map_and_totals(tab_url: str) -> tuple[dict[str, str], dict[str, int | None]]:
    """
    YouTube web sekmesinden HTML parse ederek hem video ID -> yayınlanma zamanı haritasını
    hem de kanalın gerçek tüm zamanlar toplam video/izlenme sayılarını çıkarır.
    """
    time_map: dict[str, str] = {}
    totals: dict[str, int | None] = {"total_videos": None, "total_views": None}
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

        m = re.search(r"var ytInitialData\s*=\s*({.+?});</script>", html)
        if not m:
            m = re.search(r"ytInitialData\s*=\s*({.+?});", html)
        if m:
            data = json.loads(m.group(1))
            _collect_video_times(data, time_map)
            totals = _extract_channel_totals_from_initial_data(data)
    except Exception as err:
        logger.debug("channel_tab_html_scrape_skipped", url=tab_url, error=str(err))

    return time_map, totals


def _get_channel_tab_time_map(tab_url: str) -> dict[str, str]:
    time_map, _ = _get_channel_tab_time_map_and_totals(tab_url)
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


def _format_days_ago_text(days_ago: int | None) -> tuple[str | None, str]:
    if days_ago is None:
        return None, "all_time"
    if days_ago <= 30:
        return f"{days_ago} gün önce", "month"
    if days_ago <= 365:
        return f"{max(1, days_ago // 30)} ay önce", "year"
    return f"{max(1, days_ago // 365)} yıl önce", "all_time"


def _extract_tab_entries(
    tab_url: str,
    item_type: str,
    time_map: dict[str, str],
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    opts = {
        "extract_flat": True,
        "playlist_items": "1:50",
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "socket_timeout": 8,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(tab_url, download=False) or {}
            for entry in info.get("entries", []):
                if not (entry and entry.get("title")):
                    continue
                v_id = entry.get("id")
                t_text = time_map.get(str(v_id)) if v_id else None
                days_ago = _parse_time_text_to_days(t_text) if t_text else None
                default_text, time_period = _format_days_ago_text(days_ago)
                url_prefix = "shorts/" if item_type == "short" else "watch?v="
                items.append({
                    "id": v_id,
                    "type": item_type,
                    "title": entry.get("title"),
                    "url": f"https://www.youtube.com/{url_prefix}{v_id}" if v_id else None,
                    "view_count": entry.get("view_count"),
                    "duration": entry.get("duration"),
                    "published_text": t_text or default_text,
                    "days_ago": days_ago,
                    "time_period": time_period,
                })
    except Exception as err:
        logger.warning("yt_dlp_channel_tab_extract_failed", url=tab_url, error=str(err))
    return items


def _extract_channel_sync(channel_url: str) -> dict[str, object]:
    """yt-dlp kullanarak YouTube kanalından gerçek üstverileri, genişletilmiş video ve Shorts havuzunu çeker."""
    base_url = channel_url.strip().rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://www.youtube.com/{base_url}"

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
            avatar_url = next(
                (t.get("url") for t in thumbnails if "avatar" in t.get("id", "") or "avatar" in t.get("url", "")),
                thumbnails[-1].get("url") if thumbnails else None,
            )
    except Exception as err:
        logger.warning("yt_dlp_main_channel_extract_failed", url=channel_url, error=str(err))

    video_time_map, totals = _get_channel_tab_time_map_and_totals(f"{base_url}/videos")
    shorts_time_map = _get_channel_tab_time_map(f"{base_url}/shorts")
    videos = _extract_tab_entries(f"{base_url}/videos", "video", video_time_map)
    shorts = _extract_tab_entries(f"{base_url}/shorts", "short", shorts_time_map)

    all_views = [
        int(vc)
        for v in (videos + shorts)
        for vc in [v.get("view_count")]
        if isinstance(vc, (int, float))
    ]
    sample_total_views = sum(all_views) if all_views else 0
    avg_views = round(sample_total_views / len(all_views)) if all_views else None
    analytics = compute_channel_analytics(videos, shorts)
    niche_query = infer_channel_niche_query(channel_name, description, videos, shorts)
    niche_benchmarks = _search_youtube_ytdlp_sync(niche_query, max_results=6) if niche_query else []

    real_total_videos = totals.get("total_videos") or (len(videos) + len(shorts))
    real_total_views = totals.get("total_views") or sample_total_views

    return {
        "channel_name": channel_name,
        "channel_id": channel_id,
        "channel_url": channel_url,
        "avatar_url": avatar_url,
        "description": description,
        "subscribers": subscribers,
        "subscribers_formatted": format_count(subscribers) if subscribers is not None else None,
        "channel_total_videos": real_total_videos,
        "channel_total_videos_formatted": format_count(real_total_videos),
        "channel_total_views": real_total_views,
        "channel_total_views_formatted": format_count(real_total_views) if real_total_views else None,
        "videos": videos,
        "shorts": shorts,
        "niche_query": niche_query,
        "niche_benchmarks": niche_benchmarks,
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
