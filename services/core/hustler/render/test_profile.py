"""M6 K-608: Deterministik Test Render Profili.

CI ortamında GPU garantisi olmadığından ve donanımsal encoder'lar
küçük farklılıklar üretebileceğinden, görsel regresyon testleri için
mutlak deterministik CPU encoder'ı (libx264 -crf 0) ile çalışan
test render profilidir.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
from typing import Optional

from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.generators.ffmpeg_compiler import (
    FFmpegCompiler,
    TEST_ENCODER,
)
from services.core.hustler.generators.subtitle_generator import (
    AssDocument,
    SubtitleStyle,
)
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming
from services.core.hustler.render.ffmpeg_runner import (
    FFmpegRunner,
    RenderComplete,
)


def build_test_render_command(
    template: TemplateSpec,
    audio_path: str,
    ass_path: str,
    assets: list[str],
    output_path: str,
    bg_music_path: Optional[str] = None,
    duration_sec: Optional[float] = None,
) -> list[str]:
    """Deterministik test profili ile derlenmiş FFmpeg komut dizisi üretir."""
    cmd = FFmpegCompiler.build_render_command(
        template=template,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=assets,
        output_path=output_path,
        bg_music_path=bg_music_path,
        encoder=TEST_ENCODER,
    )
    if duration_sec is not None:
        # Son parametre (çıktı dosyası) öncesine -t ekle
        cmd.insert(-1, "-t")
        cmd.insert(-1, str(duration_sec))
    return cmd


async def render_test_template(
    template: TemplateSpec,
    audio_path: str,
    ass_path: str,
    assets: list[str],
    output_path: str,
    bg_music_path: Optional[str] = None,
    duration_sec: Optional[float] = None,
    runner: Optional[FFmpegRunner] = None,
) -> str:
    """Test profiliyle render alarak deterministik videoyu üretir."""
    cmd = build_test_render_command(
        template=template,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=assets,
        output_path=output_path,
        bg_music_path=bg_music_path,
        duration_sec=duration_sec,
    )

    active_runner = runner or FFmpegRunner(
        cpu_budget=asyncio.Semaphore(1),
        target_duration_sec=duration_sec or float(template.target_duration_sec),
        timeout_sec=60.0,
    )

    completed = False
    async for event in active_runner.run(cmd, output_path):
        if isinstance(event, RenderComplete):
            completed = True

    if not completed and not Path(output_path).is_file():
        raise RuntimeError(f"Render tamamlanamadı: {output_path}")

    return output_path


def generate_synthetic_video_asset(
    path: str | Path,
    duration_sec: float = 2.0,
    width: int = 1080,
    height: int = 1920,
    pattern: str = "testsrc2",
    color: Optional[str] = None,
) -> str:
    """Senkron / deterministik test video asset'i üretir."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if color:
        lavfi_src = f"color=c={color}:s={width}x{height}:r=30:d={duration_sec}"
    else:
        lavfi_src = f"{pattern}=s={width}x{height}:r=30:d={duration_sec}"

    cmd = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner",
        "-f", "lavfi",
        "-i", lavfi_src,
        "-c:v", "libx264", "-crf", "0", "-preset", "ultrafast",
        str(out_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Sentetik video oluşturulamadı:\n{res.stderr.decode(errors='replace')}")
    return str(out_path)


def generate_synthetic_audio_asset(
    path: str | Path,
    duration_sec: float = 2.0,
    freq: int = 440,
) -> str:
    """Senkron / deterministik test ses asset'i üretir."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration_sec}",
        "-c:a", "libmp3lame",
        str(out_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Sentetik ses oluşturulamadı:\n{res.stderr.decode(errors='replace')}")
    return str(out_path)


def generate_synthetic_subtitles(
    path: str | Path,
    words: Optional[list[WordTiming]] = None,
) -> str:
    """Deterministik ASS altyazı dosyası üretir."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if words is None:
        words = [
            WordTiming(word="Hustler", start_ms=0, end_ms=900),
            WordTiming(word="Golden", start_ms=950, end_ms=1900),
        ]

    content = AssDocument.generate(
        words,
        SubtitleStyle(
            font_name="Arial",
            font_size=80,
            primary_color="&H00FFFFFF&",
            highlight_color="&H0000FFFF&",
            alignment=5,
            margin_v=50,
        ),
    )
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)
