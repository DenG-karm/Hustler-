"""M6 K-608: Altın Dosya (Golden File) Karşılaştırma Motoru.

İki video arasındaki görsel farkı FFmpeg'in dahili SSIM (Structural Similarity)
filtresi ile piksel ve kare bazında hesaplar.
Byte-to-byte / MD5 karşılaştırması yapmaz; deterministik görsel regresyon doğrulaması sağlar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Optional


@dataclass
class FrameSSIM:
    """Tek bir kareye ait SSIM ölçüm verisi."""
    frame: int
    timestamp_sec: float
    all_ssim: float
    y: float
    u: float
    v: float


@dataclass
class SSIMResult:
    """İki video arasındaki SSIM analizi çıktısı."""
    overall_ssim: float
    y_ssim: float
    u_ssim: float
    v_ssim: float
    total_frames: int
    failed_frames: list[FrameSSIM]
    min_frame_ssim: float
    worst_frame: Optional[FrameSSIM]


def get_video_fps(video_path: str | Path, default_fps: float = 30.0) -> float:
    """ffprobe ile video FPS değerini sorgular."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,avg_frame_rate",
        "-of", "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams:
                rate_str = streams[0].get("avg_frame_rate") or streams[0].get("r_frame_rate")
                if rate_str and "/" in rate_str:
                    num, den = rate_str.split("/")
                    num_f, den_f = float(num), float(den)
                    if den_f > 0:
                        fps = num_f / den_f
                        if fps > 0:
                            return fps
    except Exception:
        pass
    return default_fps


def compute_video_ssim(
    test_video_path: str | Path,
    golden_video_path: str | Path,
    min_ssim: float = 0.99,
) -> SSIMResult:
    """FFmpeg ssim filtresini çalıştırarak iki video arasındaki kare ve genel SSIM değerlerini hesaplar."""
    test_path = Path(test_video_path)
    golden_path = Path(golden_video_path)

    if not test_path.is_file():
        raise FileNotFoundError(f"Test render dosyası bulunamadı: {test_path}")
    if not golden_path.is_file():
        raise FileNotFoundError(
            f"Altın dosya bulunamadı: {golden_path}. "
            "Yeni referans oluşturmak için pytest'i --update-snapshots bayrağı ile çalıştırın."
        )

    fps = get_video_fps(golden_path)

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-i", str(test_path),
        "-i", str(golden_path),
        "-lavfi", "[0:v][1:v]ssim=stats_file=-",
        "-f", "null",
        "-",
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if proc.returncode != 0:
        err_msg = proc.stderr.strip()
        raise RuntimeError(
            f"FFmpeg SSIM hesaplama hatası (çıkış kodu: {proc.returncode}):\n{err_msg[-1000:]}"
        )

    # Kare bazlı ayrıştırma (stdout)
    # Örnek format: n:1 Y:1.000000 U:1.000000 V:1.000000 All:1.000000 (inf)
    frame_pattern = re.compile(
        r"n:(?P<frame>\d+)\s+Y:(?P<y>[\d\.]+)\s+U:(?P<u>[\d\.]+)\s+V:(?P<v>[\d\.]+)\s+All:(?P<all>[\d\.]+)"
    )

    all_frames: list[FrameSSIM] = []
    failed_frames: list[FrameSSIM] = []
    min_frame_ssim = 1.0
    worst_frame: Optional[FrameSSIM] = None

    for line in proc.stdout.splitlines():
        match = frame_pattern.search(line)
        if match:
            frame_num = int(match.group("frame"))
            y_val = float(match.group("y"))
            u_val = float(match.group("u"))
            v_val = float(match.group("v"))
            all_val = float(match.group("all"))

            # 1-indexed kare numarasına göre tahmini zaman damgası
            timestamp_sec = round((frame_num - 1) / fps, 3)

            frame_data = FrameSSIM(
                frame=frame_num,
                timestamp_sec=timestamp_sec,
                all_ssim=all_val,
                y=y_val,
                u=u_val,
                v=v_val,
            )
            all_frames.append(frame_data)

            if all_val < min_ssim:
                failed_frames.append(frame_data)

            if all_val < min_frame_ssim or worst_frame is None:
                min_frame_ssim = all_val
                worst_frame = frame_data

    total_frames = len(all_frames)
    if total_frames == 0:
        raise RuntimeError(
            f"Hiçbir kare için SSIM ölçümü alınamadı. FFmpeg çıktısı:\n{proc.stderr[-1000:]}"
        )

    # Genel SSIM değerini stderr üzerinden çek
    # Örnek format: SSIM Y:1.000000 (inf) U:1.000000 (inf) V:1.000000 (inf) All:1.000000 (inf)
    overall_pattern = re.search(
        r"SSIM\s+Y:(?P<y>[\d\.]+)\s+.*?U:(?P<u>[\d\.]+)\s+.*?V:(?P<v>[\d\.]+)\s+.*?All:(?P<all>[\d\.]+)",
        proc.stderr,
    )

    if overall_pattern:
        overall_ssim = float(overall_pattern.group("all"))
        overall_y = float(overall_pattern.group("y"))
        overall_u = float(overall_pattern.group("u"))
        overall_v = float(overall_pattern.group("v"))
    else:
        # Yedek: karelerin ortalamasını al
        overall_ssim = sum(f.all_ssim for f in all_frames) / total_frames
        overall_y = sum(f.y for f in all_frames) / total_frames
        overall_u = sum(f.u for f in all_frames) / total_frames
        overall_v = sum(f.v for f in all_frames) / total_frames

    return SSIMResult(
        overall_ssim=overall_ssim,
        y_ssim=overall_y,
        u_ssim=overall_u,
        v_ssim=overall_v,
        total_frames=total_frames,
        failed_frames=failed_frames,
        min_frame_ssim=min_frame_ssim,
        worst_frame=worst_frame,
    )


def assert_video_matches(
    test_render_path: str | Path,
    golden_path: str | Path,
    min_ssim: float = 0.99,
) -> SSIMResult:
    """İki video arasındaki SSIM benzerliğini doğrular.

    Sapma durumunda hangi karede ve kaçıncı saniyede fark olduğunu belirten
    ayrıntılı bir AssertionError fırlatır.
    """
    result = compute_video_ssim(test_render_path, golden_path, min_ssim=min_ssim)

    if result.overall_ssim < min_ssim or len(result.failed_frames) > 0:
        first_fail = result.failed_frames[0] if result.failed_frames else result.worst_frame
        worst_fail = result.worst_frame or first_fail

        first_detail = (
            f"Kare #{first_fail.frame} (~{first_fail.timestamp_sec:.2f} sn) "
            f"[SSIM: {first_fail.all_ssim:.6f} | Y: {first_fail.y:.4f}, U: {first_fail.u:.4f}, V: {first_fail.v:.4f}]"
            if first_fail else "Bilinmiyor"
        )
        worst_detail = (
            f"Kare #{worst_fail.frame} (~{worst_fail.timestamp_sec:.2f} sn) "
            f"[SSIM: {worst_fail.all_ssim:.6f} | Y: {worst_fail.y:.4f}, U: {worst_fail.u:.4f}, V: {worst_fail.v:.4f}]"
            if worst_fail else "Bilinmiyor"
        )

        msg = (
            f"\n[HATA] [Altın Dosya Görsel Regresyon Hatası] Test çıktısı altın referans ile uyuşmuyor!\n"
            f"  - Genel SSIM Skoru     : {result.overall_ssim:.6f} (Beklenen minimum: {min_ssim:.4f})\n"
            f"  - Karşılaştırılan Kare  : {result.total_frames}\n"
            f"  - Eşik Altı Kare Sayısı: {len(result.failed_frames)} adet\n"
            f"  - İlk Sapma Noktası     : {first_detail}\n"
            f"  - En Büyük Sapma        : {worst_detail}\n"
            f"  - Test Render Yolu      : {test_render_path}\n"
            f"  - Altın Dosya Yolu      : {golden_path}\n"
            f"\n[NOT] Eğer bu görsel değişim kasıtlıysa, referans altın dosyayı güncellemek için:\n"
            f"   pytest tests/test_golden_render.py --update-snapshots komutunu çalıştırın.\n"
        )
        raise AssertionError(msg)

    return result
