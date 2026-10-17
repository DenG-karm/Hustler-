from typing import List, Optional
from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.generators.ffmpeg_ast import Filter, FilterChain
from services.core.hustler.generators.transition_planner import TransitionPlanner
from services.core.hustler.generators.audio_mixer import AudioMixer
from services.core.hustler.generators.graph_validator import GraphValidator

SOFTWARE_ENCODER = "libx264"
TEST_ENCODER = "libx264_test"
DRAFT_ENCODER = "libx264_draft"

# Donanım encoder'ları (öncelik sırasıyla) ve yazılım yedeği; seçim hardware.select_video_encoder'da.
VIDEO_ENCODER_ARGS: dict[str, list[str]] = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"],
    SOFTWARE_ENCODER: ["-c:v", "libx264", "-preset", "fast", "-crf", "23"],
    TEST_ENCODER: ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "0"],
    DRAFT_ENCODER: ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "32"],
}


class FFmpegCompiler:
    """
    M6 K-603 / K-611: FFmpeg AST Derleyici (Compiler)
    TemplateSpec üzerindeki katı kuralları (çözünürlük, fps vb.) baz alarak,
    Filter, FilterChain, TransitionPlanner, AudioMixer ve GraphValidator üzerinden
    saf, deterministik ve topolojik olarak doğrulanmış bir FFmpeg komut dizisi üretir.
    """

    @staticmethod
    def _escape_ass_path(path: str) -> str:
        """Windows yollarını FFmpeg ass filtresine uyacak şekilde kaçar (escape)."""
        p = path.replace("\\", "/")
        p = p.replace(":", "\\:")
        return p

    @staticmethod
    def _resolve_encoder(profile: RenderProfile, encoder: Optional[str]) -> str:
        if encoder is not None:
            if encoder not in VIDEO_ENCODER_ARGS:
                raise ValueError(f"Desteklenmeyen video encoder'ı: {encoder}")
            return encoder

        if profile == RenderProfile.DRAFT:
            return DRAFT_ENCODER
        if profile == RenderProfile.TEST:
            return TEST_ENCODER
        return SOFTWARE_ENCODER

    @staticmethod
    def _get_profile_dimensions(template: TemplateSpec, profile: RenderProfile) -> tuple[int, int, int]:
        if profile == RenderProfile.DRAFT:
            width = max(320, template.render_config.width // 2)
            width = width - (width % 2)
            height = max(480, template.render_config.height // 2)
            height = height - (height % 2)
        else:
            width = template.render_config.width
            height = template.render_config.height
        return width, height, template.render_config.fps

    @staticmethod
    def _build_video_filters(
        assets: List[str],
        width: int,
        height: int,
        fps: int,
        ass_path: str,
        clip_durations: Optional[List[float]] = None,
        transition_sec: float = 0.5,
        profile: RenderProfile = RenderProfile.FINAL,
    ) -> list[str]:
        filters: list[str] = []
        stream_labels: list[str] = []

        transform_chain = FilterChain([
            Filter("scale", args=[f"{width}:{height}"], kwargs={"force_original_aspect_ratio": "increase"}),
            Filter("crop", args=[f"{width}:{height}"], kwargs={}),
            Filter("setsar", args=["1"], kwargs={}),
            Filter("fps", args=[str(fps)], kwargs={}),
        ])
        chain_str = transform_chain.to_string()

        for i in range(len(assets)):
            label = f"v{i}"
            filters.append(f"[{i}:v]{chain_str}[{label}]")
            stream_labels.append(label)

        if len(assets) > 1:
            if clip_durations and len(clip_durations) == len(assets) and transition_sec > 0:
                trans_lines, merged_label = TransitionPlanner.build_graph(
                    stream_labels, clip_durations, transition_sec, profile=profile
                )
                filters.extend(trans_lines)
                current_v = f"[{merged_label}]"
            else:
                concat_filter = Filter(
                    "concat",
                    args=[],
                    kwargs={"n": str(len(assets)), "v": "1", "a": "0"},
                )
                concat_inputs = "".join(f"[{lbl}]" for lbl in stream_labels)
                filters.append(f"{concat_inputs}{concat_filter.to_string()}[concat_v]")
                current_v = "[concat_v]"
        else:
            current_v = f"[{stream_labels[0]}]"

        escaped_ass = FFmpegCompiler._escape_ass_path(ass_path)
        ass_filter = Filter("ass", args=[f"'{escaped_ass}'"], kwargs={})
        filters.append(f"{current_v}{ass_filter.to_string()}[out_v]")
        return filters

    @staticmethod
    def _build_audio_filters(
        tts_idx: int,
        bg_idx: int,
        bg_music_path: Optional[str],
        use_loudnorm: bool = False,
        profile: RenderProfile = RenderProfile.FINAL,
    ) -> tuple[list[str], str]:
        if use_loudnorm:
            bg_label = f"{bg_idx}:a" if bg_music_path else None
            mix_lines, out_label = AudioMixer.build_mix_graph(
                tts_label=f"{tts_idx}:a",
                bg_label=bg_label,
                profile=profile,
            )
            mapped_out = f"[{out_label}]" if mix_lines else out_label
            return mix_lines, mapped_out

        if not bg_music_path:
            return [], f"{tts_idx}:a"

        vol_filter = Filter("volume", args=["0.1"], kwargs={})
        amix_filter = Filter(
            "amix",
            args=[],
            kwargs={"inputs": "2", "duration": "first", "dropout_transition": "2"},
        )
        filters = [
            f"[{bg_idx}:a]{vol_filter.to_string()}[bg_a]",
            f"[{tts_idx}:a][bg_a]{amix_filter.to_string()}[out_a]",
        ]
        return filters, "[out_a]"

    @staticmethod
    def build_render_command(
        template: TemplateSpec,
        audio_path: str,
        ass_path: str,
        assets: List[str],
        output_path: str,
        bg_music_path: Optional[str] = None,
        encoder: Optional[str] = None,
        profile: RenderProfile = RenderProfile.FINAL,
        duration_sec: Optional[float] = None,
        clip_durations: Optional[List[float]] = None,
        transition_sec: float = 0.5,
        use_loudnorm: bool = False,
    ) -> List[str]:
        if not assets:
            raise ValueError("En az bir görsel asset (video/resim) verilmelidir.")

        chosen_encoder = FFmpegCompiler._resolve_encoder(profile, encoder)
        width, height, fps = FFmpegCompiler._get_profile_dimensions(template, profile)

        cmd = ["ffmpeg", "-y"]
        for asset in assets:
            cmd.extend(["-i", asset])

        tts_idx = len(assets)
        cmd.extend(["-i", audio_path])

        bg_idx = len(assets) + 1 if bg_music_path else -1
        if bg_music_path:
            cmd.extend(["-i", bg_music_path])

        video_filters = FFmpegCompiler._build_video_filters(
            assets,
            width,
            height,
            fps,
            ass_path,
            clip_durations=clip_durations,
            transition_sec=transition_sec,
            profile=profile,
        )
        audio_filters, audio_map = FFmpegCompiler._build_audio_filters(
            tts_idx,
            bg_idx,
            bg_music_path,
            use_loudnorm=use_loudnorm,
            profile=profile,
        )

        all_filters = video_filters + audio_filters
        GraphValidator.validate_graph(all_filters, ["[out_v]", audio_map])

        filter_complex_str = ";".join(all_filters)

        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[out_v]",
            "-map", audio_map,
            *VIDEO_ENCODER_ARGS[chosen_encoder],
            "-c:a", "aac",
            "-b:a", "192k",
        ])
        if duration_sec is not None:
            cmd.extend(["-t", str(duration_sec)])
        cmd.append(output_path)

        return cmd
