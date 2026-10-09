"""SceneClipBuilder: ffmpeg çalıştırılmadan filtre zinciri (AST) doğrulanır."""

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.generators.scene_builder import (
    MotionRegistry,
    MotionType,
    SceneClipBuilder,
)


def test_video_chain_has_scale_crop_setsar_fps_and_no_zoompan() -> None:
    chain = SceneClipBuilder().build_clip_chain("a.mp4", is_video=True, duration=3.0)

    assert [f.name for f in chain.filters] == ["scale", "crop", "setsar", "fps"]
    text = chain.to_string()
    assert text.startswith("scale=1080:1920:force_original_aspect_ratio=increase")
    assert "zoompan" not in text


def test_image_chain_appends_zoompan_with_frame_count_for_duration() -> None:
    chain = SceneClipBuilder().build_clip_chain("a.jpg", is_video=False, duration=3.0)

    zoompan = chain.filters[-1]
    assert zoompan.name == "zoompan"
    assert zoompan.kwargs["d"] == "90"  # 3 sn * 30 fps
    assert zoompan.kwargs["s"] == "1080x1920"
    assert zoompan.kwargs["fps"] == "30"


def test_draft_profile_halves_resolution_and_skips_animation() -> None:
    chain = SceneClipBuilder().build_clip_chain(
        "a.jpg", is_video=False, duration=3.0, profile=RenderProfile.DRAFT
    )

    text = chain.to_string()
    assert "scale=540:960" in text
    assert "crop=540:960" in text
    assert "zoompan" not in text


def test_images_cycle_through_all_motion_types_in_order() -> None:
    builder = SceneClipBuilder()
    zs = [
        builder.build_clip_chain("a.jpg", is_video=False, duration=1.0).filters[-1].kwargs["z"]
        for _ in range(len(MotionType) + 1)
    ]

    expected = [MotionRegistry.get_formula(m, 1.0)["z"] for m in MotionType]
    assert zs[: len(MotionType)] == expected
    assert zs[-1] == expected[0]  # döngü başa sarar


def test_builders_do_not_share_motion_state() -> None:
    a, b = SceneClipBuilder(), SceneClipBuilder()
    a.build_clip_chain("x.jpg", is_video=False, duration=1.0)

    first_b = b.build_clip_chain("y.jpg", is_video=False, duration=1.0)

    zoom_in = MotionRegistry.get_formula(MotionType.ZOOM_IN, 1.0)
    assert first_b.filters[-1].kwargs["z"] == zoom_in["z"]


def test_motion_formula_scales_frames_with_duration_and_fps() -> None:
    formula = MotionRegistry.get_formula(MotionType.PAN_LEFT, 2.5, fps=24)

    assert formula["d"] == "60"
    assert formula["fps"] == "24"
