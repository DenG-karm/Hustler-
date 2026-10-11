"""M6 K-611: Taslak Önizleme Akışı ve Benchmark Testleri (Draft & Final Preview Benchmarks).

Katı Süre Kısıtlamaları (Hard Limits):
- DRAFT: assert draft_render_time < 10.0 (Mutlak suretle < 10 sn)
- FINAL: assert final_render_time < 120.0 (Donanım ivmelendirmeli ve CPU fallback < 120 sn)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from unittest.mock import patch
import pytest

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.domain.models.template import (
    RenderConfig,
    SafeZone,
    TemplateSpec,
)
from services.core.hustler.generators.ffmpeg_compiler import (
    DRAFT_ENCODER,
    SOFTWARE_ENCODER,
    FFmpegCompiler,
)
from services.core.hustler.render.ffmpeg_runner import (
    NvencUnavailableError,
)
from services.core.hustler.render.render_engine import (
    RenderEngine,
    render_draft,
    render_final,
)
from services.core.hustler.render.test_profile import (
    generate_synthetic_audio_asset,
    generate_synthetic_subtitles,
    generate_synthetic_video_asset,
)


@pytest.fixture
def test_template() -> TemplateSpec:
    """Benchmark için 60 saniyelik 9:16 Shorts şablonu."""
    return TemplateSpec(
        name="Benchmark Shorts 60s",
        target_duration_sec=60,
        max_scenes=5,
        allowed_tones=["ciddi"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=SafeZone(margin_top=100, margin_bottom=100, margin_left=50, margin_right=50),
        ),
    )


@pytest.fixture
def synthetic_assets(tmp_path: Path) -> dict[str, str]:
    """60 saniyelik sentetik test medyaları üretir."""
    video = generate_synthetic_video_asset(tmp_path / "input_video.mp4", duration_sec=60.0)
    audio = generate_synthetic_audio_asset(tmp_path / "input_audio.mp3", duration_sec=60.0)
    subs = generate_synthetic_subtitles(tmp_path / "input_subs.ass")
    return {"video": video, "audio": audio, "subs": subs}


def test_draft_compiler_configuration_and_filter_bypass(test_template: TemplateSpec) -> None:
    """DRAFT profili için çözünürlüğün 540x960 olduğunu ve ultrafast/crf=32 kullanıldığını doğrular."""
    cmd_draft = FFmpegCompiler.build_render_command(
        template=test_template,
        audio_path="a.mp3",
        ass_path="s.ass",
        assets=["v.mp4"],
        output_path="draft.mp4",
        profile=RenderProfile.DRAFT,
        duration_sec=60.0,
    )

    # 1. Çözünürlük 540x960 olmalı
    filter_complex = cmd_draft[cmd_draft.index("-filter_complex") + 1]
    assert "scale=540:960" in filter_complex
    assert "crop=540:960" in filter_complex

    # 2. Encoder libx264, ultrafast, crf 30+ (32) olmalı
    c_v_idx = cmd_draft.index("-c:v")
    encoder_args = cmd_draft[c_v_idx : c_v_idx + 6]
    assert encoder_args == ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"]

    # 3. Süre argümanı bulunmalı
    t_idx = cmd_draft.index("-t")
    assert cmd_draft[t_idx + 1] == "60.0"


def test_final_compiler_configuration_standard_resolution(test_template: TemplateSpec) -> None:
    """FINAL profili için çözünürlüğün tam 1080x1920 olduğunu doğrular."""
    cmd_final = FFmpegCompiler.build_render_command(
        template=test_template,
        audio_path="a.mp3",
        ass_path="s.ass",
        assets=["v.mp4"],
        output_path="final.mp4",
        profile=RenderProfile.FINAL,
    )

    filter_complex = cmd_final[cmd_final.index("-filter_complex") + 1]
    assert "scale=1080:1920" in filter_complex
    assert "crop=1080:1920" in filter_complex


@pytest.mark.asyncio
async def test_draft_render_benchmark_hard_limit_under_10_seconds(
    test_template: TemplateSpec, synthetic_assets: dict[str, str], tmp_path: Path
) -> None:
    """
    K-611 DRAFT Profil Benchmark Testi.
    KATI KURAL: 60 saniyelik video için taslak render süresi mutlak suretle < 10.0 saniye olmalıdır.
    """
    out_draft = str(tmp_path / "output_draft.mp4")

    res = await render_draft(
        template=test_template,
        audio_path=synthetic_assets["audio"],
        ass_path=synthetic_assets["subs"],
        assets=[synthetic_assets["video"]],
        output_path=out_draft,
        duration_sec=60.0,
    )

    assert res.status == "SUCCESS"
    assert res.profile == RenderProfile.DRAFT
    assert res.resolution == "540x960"
    assert Path(out_draft).is_file()
    assert Path(out_draft).stat().st_size > 0

    # KATI SÜRE ASSERTION (Limit aşılırsa test patlar)
    speed = round(60.0 / res.render_time_sec, 2)
    print(f"\n[BENCHMARK - DRAFT] Süre: {res.render_time_sec} sn | Limit: < 10.0 sn | Hız: {speed}x realtime | Çözünürlük: {res.resolution} | Encoder: {res.encoder_used}")
    assert res.render_time_sec < 10.0, (
        f"K-611 İhlali: DRAFT render süresi ({res.render_time_sec}s) 10.0 saniye limitini aştı!"
    )


@pytest.mark.asyncio
async def test_final_render_benchmark_hard_limit_under_120_seconds(
    test_template: TemplateSpec, synthetic_assets: dict[str, str], tmp_path: Path
) -> None:
    """
    K-611 FINAL Profil Donanım İvmelendirmeli Benchmark Testi.
    KATI KURAL: 60 saniyelik video için nihai render süresi < 120.0 saniye olmalıdır.
    """
    out_final = str(tmp_path / "output_final.mp4")

    res = await render_final(
        template=test_template,
        audio_path=synthetic_assets["audio"],
        ass_path=synthetic_assets["subs"],
        assets=[synthetic_assets["video"]],
        output_path=out_final,
        duration_sec=60.0,
    )

    assert res.status == "SUCCESS"
    assert res.profile == RenderProfile.FINAL
    assert res.resolution == "1080x1920"
    assert Path(out_final).is_file()
    assert Path(out_final).stat().st_size > 0

    # KATI SÜRE ASSERTION (Limit aşılırsa test patlar)
    speed = round(60.0 / res.render_time_sec, 2)
    print(f"\n[BENCHMARK - FINAL HW] Süre: {res.render_time_sec} sn | Limit: < 120.0 sn | Hız: {speed}x realtime | Çözünürlük: {res.resolution} | Encoder: {res.encoder_used}")
    assert res.render_time_sec < 120.0, (
        f"K-611 İhlali: FINAL render süresi ({res.render_time_sec}s) 120.0 saniye limitini aştı!"
    )


@pytest.mark.asyncio
async def test_final_cpu_fallback_benchmark_hard_limit_under_120_seconds(
    test_template: TemplateSpec, synthetic_assets: dict[str, str], tmp_path: Path
) -> None:
    """
    K-611 FINAL Profil CPU Fallback Benchmark Testi.
    KATI KURAL: GPU yokluğunda veya arızasında CPU fallback render süresi de < 120.0 saniye olmalıdır.
    """
    out_cpu = str(tmp_path / "output_cpu.mp4")

    res = await render_final(
        template=test_template,
        audio_path=synthetic_assets["audio"],
        ass_path=synthetic_assets["subs"],
        assets=[synthetic_assets["video"]],
        output_path=out_cpu,
        duration_sec=60.0,
        force_cpu=True,
    )

    assert res.status == "SUCCESS"
    assert res.profile == RenderProfile.FINAL
    assert res.encoder_used == SOFTWARE_ENCODER
    assert res.resolution == "1080x1920"
    assert Path(out_cpu).is_file()

    # KATI SÜRE ASSERTION (Limit aşılırsa test patlar)
    speed = round(60.0 / res.render_time_sec, 2)
    print(f"\n[BENCHMARK - FINAL CPU FALLBACK] Süre: {res.render_time_sec} sn | Limit: < 120.0 sn | Hız: {speed}x realtime | Çözünürlük: {res.resolution} | Encoder: {res.encoder_used}")
    assert res.render_time_sec < 120.0, (
        f"K-611 İhlali: CPU Fallback render süresi ({res.render_time_sec}s) 120.0 saniye limitini aştı!"
    )


@pytest.mark.asyncio
async def test_hardware_failure_automatically_recovers_to_cpu(
    test_template: TemplateSpec, synthetic_assets: dict[str, str], tmp_path: Path
) -> None:
    """
    Donanım encoder'ı hata verdiğinde motorun otomatik olarak CPU fallback'e geçtiğini doğrular.
    """
    out_fallback = str(tmp_path / "output_fallback.mp4")
    engine = RenderEngine()

    call_count = 0
    orig_execute = engine._execute_ffmpeg

    async def flaky_execute(cmd: list[str], output_path: str, target_duration_sec: float, timeout_sec: float = 300.0) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise NvencUnavailableError("NVENC cihazı başlatılamadı.", "Simulated NVENC error")
        await orig_execute(cmd, output_path, target_duration_sec, timeout_sec)

    with patch("services.core.hustler.render.render_engine.select_video_encoder", return_value="h264_nvenc"):
        with patch.object(engine, "_execute_ffmpeg", side_effect=flaky_execute):
            res = await engine.render_final(
                template=test_template,
                audio_path=synthetic_assets["audio"],
                ass_path=synthetic_assets["subs"],
                assets=[synthetic_assets["video"]],
                output_path=out_fallback,
                duration_sec=2.0,  # Hızlı doğrulama için 2 saniye
            )

    assert call_count == 2, "Donanım hatasında ikinci kez (CPU ile) çağrılmalıdır."
    assert res.fallback_occurred is True
    assert res.encoder_used == SOFTWARE_ENCODER
    assert res.status == "SUCCESS"
    assert res.resolution == "1080x1920"
    assert Path(out_fallback).is_file()
