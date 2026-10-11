"""M6 K-611 E2E Render ve Önizleme Benchmark Çalıştırıcısı.

Bu betik, 60 saniyelik bir video üzerinde:
1. DRAFT Profilini (< 10.0 sn, 540x960, ultrafast, crf 32)
2. FINAL Profilini (< 120.0 sn, 1080x1920, Donanım Hızlandırmalı NVENC/AMF)
3. FINAL CPU Fallback Profilini (< 120.0 sn, 1080x1920, libx264 fast)
uçtan uca çalıştırır, süreleri ölçer ve katı limitleri (hard-limit) doğrular.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.domain.models.template import (
    RenderConfig,
    SafeZone,
    TemplateSpec,
)
from services.core.hustler.infrastructure.hardware import detect_cuda, select_video_encoder
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming
from services.core.hustler.render.render_engine import RenderEngine
from services.core.hustler.render.test_profile import (
    generate_synthetic_audio_asset,
    generate_synthetic_subtitles,
    generate_synthetic_video_asset,
)


def make_benchmark_template(duration_sec: int = 60) -> TemplateSpec:
    return TemplateSpec(
        name="K-611 Benchmark 60s Shorts",
        target_duration_sec=duration_sec,
        max_scenes=6,
        allowed_tones=["ciddi"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=SafeZone(margin_top=100, margin_bottom=100, margin_left=50, margin_right=50),
        ),
    )


async def main() -> int:
    out_dir = REPO_ROOT / "e2e_out" / "k611_benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" HUSTLER M6 K-611: E2E RENDER & ÖNİZLEME BENCHMARK")
    print("=" * 80)

    # 1. Donanım Taraması
    cuda_available = await detect_cuda()
    hw_encoder = await select_video_encoder()
    print(f"[*] CUDA/NVIDIA GPU Mevcut : {cuda_available}")
    print(f"[*] Seçilen Video Encoder : {hw_encoder}")

    # 2. Sentetik Test Varlıkları (60 sn)
    print("\n[*] 60 saniyelik test medyaları hazırlanıyor...")
    video_path = out_dir / "bench_input_video.mp4"
    audio_path = out_dir / "bench_input_audio.mp3"
    subs_path = out_dir / "bench_input_subs.ass"

    generate_synthetic_video_asset(video_path, duration_sec=60.0, width=1080, height=1920)
    generate_synthetic_audio_asset(audio_path, duration_sec=60.0)

    # Geçerli kelime zamanlamaları (Fail-fast Circuit Breaker uyumlu)
    words = [
        WordTiming(word=f"Kelime_{i}", start_ms=i * 1000, end_ms=(i * 1000) + 900)
        for i in range(60)
    ]
    generate_synthetic_subtitles(subs_path, words=words)
    print("[+] Test medyaları hazırlandı (Video: 1080x1920 60s, Audio: 60s, Subs: 60 kelime).")

    template = make_benchmark_template(60)
    engine = RenderEngine()

    results = []

    # 3. DRAFT Profil Benchmark (< 10.0 sn)
    print("\n" + "-" * 80)
    print(" [1/3] DRAFT PROFİLİ ÖNİZLEME BENCHMARK (Hedef: < 10.0 sn)")
    print("-" * 80)
    draft_out = str(out_dir / "bench_output_draft.mp4")
    res_draft = await engine.render_draft(
        template=template,
        audio_path=str(audio_path),
        ass_path=str(subs_path),
        assets=[str(video_path)],
        output_path=draft_out,
        duration_sec=60.0,
    )
    speed_draft = round(60.0 / res_draft.render_time_sec, 2)
    draft_passed = res_draft.render_time_sec < 10.0 and res_draft.resolution == "540x960"
    results.append({
        "profile": "DRAFT Önizleme",
        "limit": "< 10.0 sn",
        "time": f"{res_draft.render_time_sec:.3f} sn",
        "speed": f"{speed_draft}x realtime",
        "resolution": res_draft.resolution,
        "encoder": res_draft.encoder_used,
        "status": "PASS" if draft_passed else "FAIL",
    })
    print(f"  -> Süre       : {res_draft.render_time_sec:.3f} sn (Limit: < 10.0 sn)")
    print(f"  -> Hız        : {speed_draft}x realtime")
    print(f"  -> Çözünürlük : {res_draft.resolution} (Hedef: 540x960)")
    print(f"  -> Encoder    : {res_draft.encoder_used}")
    print(f"  -> Durum      : {'PASS' if draft_passed else 'FAIL'}")
    assert draft_passed, f"DRAFT süre aşımı: {res_draft.render_time_sec}s >= 10.0s"

    # 4. FINAL Donanım İvmelendirmeli Benchmark (< 120.0 sn)
    print("\n" + "-" * 80)
    print(f" [2/3] FINAL DONANIM İVMELENDİRMELİ BENCHMARK ({hw_encoder}, Hedef: < 120.0 sn)")
    print("-" * 80)
    final_out = str(out_dir / "bench_output_final_hw.mp4")
    res_final_hw = await engine.render_final(
        template=template,
        audio_path=str(audio_path),
        ass_path=str(subs_path),
        assets=[str(video_path)],
        output_path=final_out,
        duration_sec=60.0,
        force_cpu=False,
    )
    speed_hw = round(60.0 / res_final_hw.render_time_sec, 2)
    final_hw_passed = res_final_hw.render_time_sec < 120.0 and res_final_hw.resolution == "1080x1920"
    results.append({
        "profile": f"FINAL ({res_final_hw.encoder_used})",
        "limit": "< 120.0 sn",
        "time": f"{res_final_hw.render_time_sec:.3f} sn",
        "speed": f"{speed_hw}x realtime",
        "resolution": res_final_hw.resolution,
        "encoder": res_final_hw.encoder_used,
        "status": "PASS" if final_hw_passed else "FAIL",
    })
    print(f"  -> Süre       : {res_final_hw.render_time_sec:.3f} sn (Limit: < 120.0 sn)")
    print(f"  -> Hız        : {speed_hw}x realtime")
    print(f"  -> Çözünürlük : {res_final_hw.resolution} (Hedef: 1080x1920)")
    print(f"  -> Encoder    : {res_final_hw.encoder_used}")
    print(f"  -> Fallback?  : {res_final_hw.fallback_occurred}")
    print(f"  -> Durum      : {'PASS' if final_hw_passed else 'FAIL'}")
    assert final_hw_passed, f"FINAL HW süre aşımı: {res_final_hw.render_time_sec}s >= 120.0s"

    # 5. FINAL CPU Fallback Benchmark (< 120.0 sn)
    print("\n" + "-" * 80)
    print(" [3/3] FINAL CPU FALLBACK BENCHMARK (libx264, Hedef: < 120.0 sn)")
    print("-" * 80)
    cpu_out = str(out_dir / "bench_output_final_cpu.mp4")
    res_cpu = await engine.render_final(
        template=template,
        audio_path=str(audio_path),
        ass_path=str(subs_path),
        assets=[str(video_path)],
        output_path=cpu_out,
        duration_sec=60.0,
        force_cpu=True,
    )
    speed_cpu = round(60.0 / res_cpu.render_time_sec, 2)
    cpu_passed = res_cpu.render_time_sec < 120.0 and res_cpu.resolution == "1080x1920"
    results.append({
        "profile": "FINAL (CPU Fallback)",
        "limit": "< 120.0 sn",
        "time": f"{res_cpu.render_time_sec:.3f} sn",
        "speed": f"{speed_cpu}x realtime",
        "resolution": res_cpu.resolution,
        "encoder": res_cpu.encoder_used,
        "status": "PASS" if cpu_passed else "FAIL",
    })
    print(f"  -> Süre       : {res_cpu.render_time_sec:.3f} sn (Limit: < 120.0 sn)")
    print(f"  -> Hız        : {speed_cpu}x realtime")
    print(f"  -> Çözünürlük : {res_cpu.resolution} (Hedef: 1080x1920)")
    print(f"  -> Encoder    : {res_cpu.encoder_used}")
    print(f"  -> Durum      : {'PASS' if cpu_passed else 'FAIL'}")
    assert cpu_passed, f"FINAL CPU süre aşımı: {res_cpu.render_time_sec}s >= 120.0s"

    # 6. Özet Rapor Tablosu
    print("\n" + "=" * 80)
    print(" K-611 E2E BENCHMARK ÖZET TABLOSU")
    print("=" * 80)
    print(f"{'Profil':<24} | {'Limit':<10} | {'Ölçülen Süre':<12} | {'Hız':<14} | {'Çözünürlük':<10} | {'Durum'}")
    print("-" * 80)
    for r in results:
        print(f"{r['profile']:<24} | {r['limit']:<10} | {r['time']:<12} | {r['speed']:<14} | {r['resolution']:<10} | {r['status']}")
    print("=" * 80)

    all_passed = all(r["status"] == "PASS" for r in results)
    print(f"\nSONUÇ: {'TÜM K-611 BENCHMARK SÜRELERİ BAŞARIYLA KANITLANDI!' if all_passed else 'BAZI BENCHMARK TESTLERİ BAŞARISIZ OLDU!'}\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
