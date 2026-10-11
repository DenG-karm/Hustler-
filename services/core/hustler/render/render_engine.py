"""M6 K-611: Taslak ve Nihai Render Motoru (Preview & Render Pipeline Engine).

- DRAFT Profili: Çözünürlük 540x960'a düşürülür, preset=ultrafast, crf=32.
  Ağır efektler (xfade, loudnorm, zoompan) by-pass edilir.
  Hedef süre: mutlak suretle < 10.0 saniye.

- FINAL Profili: Donanım hızlandırması (NVENC/AMF) denenir; hata veya donanım
  yokluğunda otomatik olarak CPU (libx264 -preset fast -crf 23) fallback uygulanır.
  Hedef süre: < 120.0 saniye.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Optional

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.generators.ffmpeg_compiler import (
    DRAFT_ENCODER,
    SOFTWARE_ENCODER,
    FFmpegCompiler,
)
from services.core.hustler.infrastructure.hardware import select_video_encoder
from services.core.hustler.render.ffmpeg_runner import (
    FFmpegRunner,
    RenderComplete,
)
from services.core.hustler.validation.slot_validator import probe_media_file

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """Render işlemi sonucu ve benchmark metrikleri."""
    output_path: str
    profile: RenderProfile
    render_time_sec: float
    target_duration_sec: float
    encoder_used: str
    resolution: str
    fallback_occurred: bool = False
    status: str = "SUCCESS"
    error: Optional[str] = None


class RenderEngine:
    """M6 K-611 Render ve Önizleme Yürütme Motoru."""

    def __init__(self, cpu_budget: Optional[asyncio.Semaphore] = None) -> None:
        self.cpu_budget = cpu_budget or asyncio.Semaphore(1)

    async def _execute_ffmpeg(
        self,
        cmd: list[str],
        output_path: str,
        target_duration_sec: float,
        timeout_sec: float = 300.0,
    ) -> None:
        """FFmpegRunner ile komutu çalıştırır."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if out_p.exists():
            out_p.unlink()
        part_p = Path(output_path + ".part")
        if part_p.exists():
            part_p.unlink()

        runner = FFmpegRunner(
            cpu_budget=self.cpu_budget,
            target_duration_sec=target_duration_sec,
            timeout_sec=timeout_sec,
        )

        completed = False
        async for event in runner.run(cmd, output_path):
            if isinstance(event, RenderComplete):
                completed = True

        if not completed and not out_p.is_file():
            raise RuntimeError(f"Render tamamlanamadı ve çıktı üretilemedi: {output_path}")

    async def render_draft(
        self,
        template: TemplateSpec,
        audio_path: str,
        ass_path: str,
        assets: list[str],
        output_path: str,
        bg_music_path: Optional[str] = None,
        duration_sec: Optional[float] = None,
    ) -> RenderResult:
        """DRAFT profilinde hızlı taslak önizleme render'ı alır (Hedef: < 10.0 sn)."""
        dur = duration_sec or float(template.target_duration_sec)
        t0 = time.perf_counter()

        cmd = FFmpegCompiler.build_render_command(
            template=template,
            audio_path=audio_path,
            ass_path=ass_path,
            assets=assets,
            output_path=output_path,
            bg_music_path=bg_music_path,
            encoder=DRAFT_ENCODER,
            profile=RenderProfile.DRAFT,
            duration_sec=duration_sec,
        )

        await self._execute_ffmpeg(
            cmd=cmd,
            output_path=output_path,
            target_duration_sec=dur,
            timeout_sec=30.0,
        )

        elapsed = time.perf_counter() - t0
        _, w, h = probe_media_file(output_path)
        res_str = f"{w}x{h}" if w and h else "unknown"

        return RenderResult(
            output_path=output_path,
            profile=RenderProfile.DRAFT,
            render_time_sec=round(elapsed, 3),
            target_duration_sec=dur,
            encoder_used=DRAFT_ENCODER,
            resolution=res_str,
            fallback_occurred=False,
            status="SUCCESS",
        )

    async def render_final(
        self,
        template: TemplateSpec,
        audio_path: str,
        ass_path: str,
        assets: list[str],
        output_path: str,
        bg_music_path: Optional[str] = None,
        duration_sec: Optional[float] = None,
        force_cpu: bool = False,
    ) -> RenderResult:
        """FINAL profilinde donanım ivmelendirmeli veya CPU fallback'li nihai render alır (Hedef: < 120.0 sn)."""
        dur = duration_sec or float(template.target_duration_sec)
        t0 = time.perf_counter()

        encoder = SOFTWARE_ENCODER if force_cpu else await select_video_encoder()
        fallback_occurred = False

        if encoder != SOFTWARE_ENCODER:
            # Donanım ivmelendirmesi ile dene
            cmd_hw = FFmpegCompiler.build_render_command(
                template=template,
                audio_path=audio_path,
                ass_path=ass_path,
                assets=assets,
                output_path=output_path,
                bg_music_path=bg_music_path,
                encoder=encoder,
                profile=RenderProfile.FINAL,
                duration_sec=duration_sec,
            )
            try:
                await self._execute_ffmpeg(
                    cmd=cmd_hw,
                    output_path=output_path,
                    target_duration_sec=dur,
                    timeout_sec=180.0,
                )
            except Exception as exc:
                logger.warning(
                    "Donanım encoder'ı (%s) başarısız oldu, CPU fallback uygulanıyor: %s",
                    encoder,
                    exc,
                )
                fallback_occurred = True
                encoder = SOFTWARE_ENCODER

        if encoder == SOFTWARE_ENCODER:
            cmd_cpu = FFmpegCompiler.build_render_command(
                template=template,
                audio_path=audio_path,
                ass_path=ass_path,
                assets=assets,
                output_path=output_path,
                bg_music_path=bg_music_path,
                encoder=SOFTWARE_ENCODER,
                profile=RenderProfile.FINAL,
                duration_sec=duration_sec,
            )
            await self._execute_ffmpeg(
                cmd=cmd_cpu,
                output_path=output_path,
                target_duration_sec=dur,
                timeout_sec=240.0,
            )

        elapsed = time.perf_counter() - t0
        _, w, h = probe_media_file(output_path)
        res_str = f"{w}x{h}" if w and h else "unknown"

        return RenderResult(
            output_path=output_path,
            profile=RenderProfile.FINAL,
            render_time_sec=round(elapsed, 3),
            target_duration_sec=dur,
            encoder_used=encoder,
            resolution=res_str,
            fallback_occurred=fallback_occurred,
            status="SUCCESS",
        )


async def render_draft(
    template: TemplateSpec,
    audio_path: str,
    ass_path: str,
    assets: list[str],
    output_path: str,
    bg_music_path: Optional[str] = None,
    duration_sec: Optional[float] = None,
    cpu_budget: Optional[asyncio.Semaphore] = None,
) -> RenderResult:
    """Taslak önizleme render yardımcı fonksiyonu."""
    engine = RenderEngine(cpu_budget=cpu_budget)
    return await engine.render_draft(
        template=template,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=assets,
        output_path=output_path,
        bg_music_path=bg_music_path,
        duration_sec=duration_sec,
    )


async def render_final(
    template: TemplateSpec,
    audio_path: str,
    ass_path: str,
    assets: list[str],
    output_path: str,
    bg_music_path: Optional[str] = None,
    duration_sec: Optional[float] = None,
    force_cpu: bool = False,
    cpu_budget: Optional[asyncio.Semaphore] = None,
) -> RenderResult:
    """Nihai render yardımcı fonksiyonu (Donanım ivmelendirmeli + CPU Fallback)."""
    engine = RenderEngine(cpu_budget=cpu_budget)
    return await engine.render_final(
        template=template,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=assets,
        output_path=output_path,
        bg_music_path=bg_music_path,
        duration_sec=duration_sec,
        force_cpu=force_cpu,
    )
