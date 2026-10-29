from __future__ import annotations

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def _format_count(count: int | float | None) -> str:
    """Sayısal veriyi (ör: 6630000) insan tarafından okunabilir metne dönüştürür (6.63M)."""
    if count is None:
        return "0"
    val = float(count)
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(int(val))


def _compute_line_chart_for_items(items: list[dict[str, object]], item_type: str) -> dict[str, object]:
    """
    Belirli bir içerik türü (video veya short) için Pandas ve NumPy kullanarak
    zaman serisi hareketli ortalamasını ve eğimini hesaplar.
    """
    if not items:
        return {
            "points": [],
            "max_val": 0,
            "min_val": 0,
            "avg_val": 0,
            "avg_val_formatted": "0",
            "trend_direction": "stable",
        }

    df = pd.DataFrame(items)
    if "view_count" not in df.columns:
        df["view_count"] = 0
    else:
        df["view_count"] = pd.to_numeric(df["view_count"], errors="coerce").fillna(0).astype(float)

    # 3-öğe hareketli ortalama (Pandas rolling window)
    df["rolling_avg"] = df["view_count"].rolling(window=3, min_periods=1).mean()

    views_array = df["view_count"].to_numpy(dtype=float)
    max_views = float(np.max(views_array)) if len(views_array) > 0 else 0.0
    min_views = float(np.min(views_array)) if len(views_array) > 0 else 0.0
    avg_views = float(np.mean(views_array)) if len(views_array) > 0 else 0.0

    # Trend eğimi hesabı (NumPy linear fit / polyfit)
    trend_direction = "stable"
    if len(views_array) >= 2:
        x_indices = np.arange(len(views_array))
        slope, _ = np.polyfit(x_indices, views_array, 1)
        thresh = 0.05 * (max_views if max_views > 0 else 1)
        if slope > thresh:
            trend_direction = "up"
        elif slope < -thresh:
            trend_direction = "down"

    line_points = []
    for idx, row in df.iterrows():
        v_count = int(row["view_count"])
        r_avg = float(row["rolling_avg"])
        line_points.append({
            "index": int(idx) + 1,
            "id": row.get("id"),
            "title": str(row.get("title") or item_type.capitalize()),
            "type": item_type,
            "view_count": v_count,
            "view_count_formatted": _format_count(v_count),
            "rolling_avg": round(r_avg, 1),
            "rolling_avg_formatted": _format_count(r_avg),
        })

    return {
        "points": line_points,
        "max_val": int(max_views),
        "min_val": int(min_views),
        "avg_val": round(avg_views, 1),
        "avg_val_formatted": _format_count(avg_views),
        "trend_direction": trend_direction,
    }


def _compute_outliers_and_tiers(
    all_items: list[dict[str, object]], avg_views: float
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """
    1) Viral Çarpan (Outliers): Kanal ortalamasına göre en yüksek çarpanlı (Nx) ilk 6 içeriği çıkarır.
    2) İzlenme Kademesi (View Tiers): İçeriklerin izlenme aralıklarına göre dağılımını hesaplar.
    """
    base_avg = max(1.0, avg_views)
    sorted_items = sorted(all_items, key=lambda x: float(str(x.get("view_count") or 0)), reverse=True)
    outliers: list[dict[str, object]] = []
    for item in sorted_items[:6]:
        vc = int(float(str(item.get("view_count") or 0)))
        mult = round(vc / base_avg, 2)
        outliers.append({
            "id": item.get("id"),
            "title": str(item.get("title") or "İçerik"),
            "type": str(item.get("type") or "video"),
            "view_count": vc,
            "view_count_formatted": _format_count(vc),
            "multiplier": mult,
            "multiplier_formatted": f"{mult:.1f}x",
        })

    total_cnt = max(1, len(all_items))
    tier_defs = [
        ("0 - 10K", 0, 10_000),
        ("10K - 50K", 10_000, 50_000),
        ("50K - 250K", 50_000, 250_000),
        ("250K+", 250_000, 10**15),
    ]
    tiers: list[dict[str, object]] = []
    for label, low, high in tier_defs:
        cnt = sum(
            1
            for it in all_items
            if low <= int(float(str(it.get("view_count") or 0))) < high
        )
        tiers.append({
            "label": label,
            "count": cnt,
            "percentage": round((cnt / total_cnt) * 100, 1),
        })
    return outliers, tiers


def compute_channel_analytics(
    videos: list[dict[str, object]], shorts: list[dict[str, object]]
) -> dict[str, object]:
    """
    Pandas ve NumPy kullanarak kanalın çekilen gerçek videolarından
    ayrı ayrı Uzun Video Çizgi Grafiği, Shorts Çizgi Grafiği ve Format Daire Grafiği üretir.
    """
    clean_videos = [
        {
            "id": v.get("id"),
            "title": v.get("title") or "Video",
            "type": "video",
            "view_count": v.get("view_count") if isinstance(v.get("view_count"), (int, float)) else 0,
            "duration": v.get("duration") or 0,
        }
        for v in videos
    ]

    clean_shorts = [
        {
            "id": s.get("id"),
            "title": s.get("title") or "Shorts",
            "type": "short",
            "view_count": s.get("view_count") if isinstance(s.get("view_count"), (int, float)) else 0,
            "duration": s.get("duration") or 0,
        }
        for s in shorts
    ]

    all_items = clean_videos + clean_shorts

    empty_line = {"points": [], "max_val": 0, "min_val": 0, "avg_val": 0, "avg_val_formatted": "0", "trend_direction": "stable"}

    if not all_items:
        return {
            "has_data": False,
            "line_chart": empty_line,
            "videos_line_chart": empty_line,
            "shorts_line_chart": empty_line,
            "pie_chart": {"slices": [], "total_views": 0, "total_views_formatted": "0"},
            "outliers": [],
            "view_tiers": [],
            "summary": {"median_views": 0, "max_views": 0, "min_views": 0, "total_views": 0},
            "videos_summary": {"median_views": 0, "max_views": 0, "min_views": 0, "total_views": 0, "sample_count": 0},
            "shorts_summary": {"median_views": 0, "max_views": 0, "min_views": 0, "total_views": 0, "sample_count": 0},
        }

    # 1. Uzun Videolar İçin Ayrı Çizgi Grafiği (Pandas & NumPy)
    videos_line_chart = _compute_line_chart_for_items(clean_videos, "video")

    # 2. Shorts Videoları İçin Ayrı Çizgi Grafiği (Pandas & NumPy)
    shorts_line_chart = _compute_line_chart_for_items(clean_shorts, "short")

    # 3. Genel Toplu Çizgi Grafiği (Geriye Dönük Uyumluluk)
    df_all = pd.DataFrame(all_items)
    df_all["rolling_avg"] = df_all["view_count"].rolling(window=3, min_periods=1).mean()
    views_array = df_all["view_count"].to_numpy(dtype=float)
    max_views = float(np.max(views_array)) if len(views_array) > 0 else 0.0
    min_views = float(np.min(views_array)) if len(views_array) > 0 else 0.0
    median_views = float(np.median(views_array)) if len(views_array) > 0 else 0.0
    avg_views = float(np.mean(views_array)) if len(views_array) > 0 else 0.0
    total_views = float(np.sum(views_array)) if len(views_array) > 0 else 0.0

    overall_trend = "stable"
    if len(views_array) >= 2:
        x_indices = np.arange(len(views_array))
        slope, _ = np.polyfit(x_indices, views_array, 1)
        thresh = 0.05 * (max_views if max_views > 0 else 1)
        if slope > thresh:
            overall_trend = "up"
        elif slope < -thresh:
            overall_trend = "down"

    line_points = []
    for idx, row in df_all.iterrows():
        v_count = int(row["view_count"])
        r_avg = float(row["rolling_avg"])
        line_points.append({
            "index": int(idx) + 1,
            "id": row["id"],
            "title": str(row["title"]),
            "type": str(row["type"]),
            "view_count": v_count,
            "view_count_formatted": _format_count(v_count),
            "rolling_avg": round(r_avg, 1),
            "rolling_avg_formatted": _format_count(r_avg),
        })

    # 4. Daire Grafiği Veri Noktaları (Pie/Donut Chart / Format ve İzlenme Payı)
    grouped = df_all.groupby("type")["view_count"].agg(["sum", "count"]).reset_index()

    slices = []
    color_map = {
        "video": {"color": "#3B82F6", "label": "Yatay Video", "bg": "bg-blue-500"},
        "short": {"color": "#06B6D4", "label": "Dikey Shorts", "bg": "bg-cyan-500"},
    }

    for _, row in grouped.iterrows():
        item_type = str(row["type"])
        item_sum = float(row["sum"])
        item_count = int(row["count"])
        pct = round((item_sum / total_views * 100), 1) if total_views > 0 else 0.0
        meta = color_map.get(item_type, {"color": "#10B981", "label": item_type.capitalize(), "bg": "bg-emerald-500"})

        slices.append({
            "type": item_type,
            "label": meta["label"],
            "color": meta["color"],
            "count": item_count,
            "total_views": int(item_sum),
            "total_views_formatted": _format_count(item_sum),
            "percentage": pct,
        })

    slices.sort(key=lambda s: float(str(s["percentage"])), reverse=True)
    outliers, view_tiers = _compute_outliers_and_tiers(all_items, avg_views)

    return {
        "has_data": True,
        "line_chart": {
            "points": line_points,
            "max_val": int(max_views),
            "min_val": int(min_views),
            "avg_val": round(avg_views, 1),
            "avg_val_formatted": _format_count(avg_views),
            "trend_direction": overall_trend,
        },
        "videos_line_chart": videos_line_chart,
        "shorts_line_chart": shorts_line_chart,
        "pie_chart": {
            "slices": slices,
            "total_views": int(total_views),
            "total_views_formatted": _format_count(total_views),
        },
        "outliers": outliers,
        "view_tiers": view_tiers,
        "summary": {
            "median_views": int(median_views),
            "median_views_formatted": _format_count(median_views),
            "max_views": int(max_views),
            "max_views_formatted": _format_count(max_views),
            "min_views": int(min_views),
            "total_views": int(total_views),
            "total_views_formatted": _format_count(total_views),
            "sample_count": len(all_items),
        },
    }
