"""FFmpegCompiler: komut dizisi harf harf doğrulanır; üretilen graf GraphValidator'dan geçer."""

import pytest

from services.core.hustler.domain.models.template import TemplateSpec
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler
from services.core.hustler.generators.graph_validator import GraphValidator

SCALE = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
ENCODE = [
    "-c:v",
    "libx264",
    "-preset",
    "fast",
    "-crf",
    "23",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
]


def _graph(cmd: list[str]) -> list[str]:
    return cmd[cmd.index("-filter_complex") + 1].split(";")


def test_single_asset_without_music_produces_exact_command(
    template: TemplateSpec,
) -> None:
    cmd = FFmpegCompiler.build_render_command(
        template, "tts.mp3", "C:\\subs\\x.ass", ["a.mp4"], "out.mp4"
    )

    assert cmd == [
        "ffmpeg",
        "-y",
        "-i",
        "a.mp4",
        "-i",
        "tts.mp3",
        "-filter_complex",
        f"[0:v]{SCALE}[v0];[v0]ass='C\\:/subs/x.ass'[out_v]",
        "-map",
        "[out_v]",
        "-map",
        "1:a",
        *ENCODE,
        "out.mp4",
    ]


def test_two_assets_with_music_concat_and_mix_audio_exactly(
    template: TemplateSpec,
) -> None:
    cmd = FFmpegCompiler.build_render_command(
        template,
        "tts.mp3",
        "s.ass",
        ["a.mp4", "b.jpg"],
        "out.mp4",
        bg_music_path="bg.mp3",
    )

    assert cmd[:10] == [
        "ffmpeg",
        "-y",
        "-i",
        "a.mp4",
        "-i",
        "b.jpg",
        "-i",
        "tts.mp3",
        "-i",
        "bg.mp3",
    ]
    assert _graph(cmd) == [
        f"[0:v]{SCALE}[v0]",
        f"[1:v]{SCALE}[v1]",
        "[v0][v1]concat=n=2:v=1:a=0[concat_v]",
        "[concat_v]ass='s.ass'[out_v]",
        "[3:a]volume=0.1[bg_a]",
        "[2:a][bg_a]amix=inputs=2:duration=first:dropout_transition=2[out_a]",
    ]
    assert cmd[cmd.index("-map", cmd.index("[out_v]")) + 1] == "[out_a]"


@pytest.mark.parametrize("assets", [1, 2, 5])
@pytest.mark.parametrize("music", [None, "bg.mp3"])
def test_generated_graph_is_topologically_valid(
    template: TemplateSpec, assets: int, music: str | None
) -> None:
    cmd = FFmpegCompiler.build_render_command(
        template, "t.mp3", "s.ass", [f"{i}.mp4" for i in range(assets)], "o.mp4", music
    )
    maps = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"]

    GraphValidator.validate_graph(_graph(cmd), maps)


def test_empty_asset_list_raises_value_error(template: TemplateSpec) -> None:
    with pytest.raises(ValueError, match="En az bir"):
        FFmpegCompiler.build_render_command(template, "t.mp3", "s.ass", [], "o.mp4")


@pytest.mark.parametrize(
    ("raw", "escaped"),
    [
        ("C:\\a\\b.ass", "C\\:/a/b.ass"),
        ("rel/path.ass", "rel/path.ass"),
        ("", ""),
        ("a:b:c", "a\\:b\\:c"),
    ],
)
def test_ass_path_escaping(raw: str, escaped: str) -> None:
    assert FFmpegCompiler._escape_ass_path(raw) == escaped


def test_command_building_is_deterministic(template: TemplateSpec) -> None:
    args = (template, "t.mp3", "s.ass", ["a.mp4", "b.mp4"], "o.mp4")

    assert FFmpegCompiler.build_render_command(
        *args
    ) == FFmpegCompiler.build_render_command(*args)
