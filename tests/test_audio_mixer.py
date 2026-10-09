"""AudioMixer: loudnorm/amix graf metni harf harf; profil davranışı."""

import pytest

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.generators.audio_mixer import AudioMixer
from services.core.hustler.generators.graph_validator import GraphValidator

LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
AMIX = "amix=inputs=2:duration=first:dropout_transition=2"


def test_loudnorm_filter_uses_broadcast_targets() -> None:
    assert AudioMixer.get_loudnorm_filter().to_string() == LOUDNORM


def test_final_with_music_normalizes_both_ducks_music_and_mixes() -> None:
    lines, out = AudioMixer.build_mix_graph("tts", "bg")

    assert lines == [
        f"[tts]{LOUDNORM}[tts_norm]",
        f"[bg]{LOUDNORM}[bg_norm]",
        "[bg_norm]volume=0.1[bg_vol]",
        f"[tts_norm][bg_vol]{AMIX}[audio_out]",
    ]
    assert out == "audio_out"
    GraphValidator.validate_graph(lines, [f"[{out}]"])


def test_final_without_music_only_normalizes_tts() -> None:
    assert AudioMixer.build_mix_graph("tts") == (
        [f"[tts]{LOUDNORM}[tts_norm]"],
        "tts_norm",
    )


def test_draft_skips_loudnorm_but_still_ducks_and_mixes() -> None:
    lines, out = AudioMixer.build_mix_graph("tts", "bg", RenderProfile.DRAFT)

    assert lines == ["[bg]volume=0.1[bg_vol]", f"[tts][bg_vol]{AMIX}[audio_out]"]
    assert out == "audio_out"
    assert all("loudnorm" not in line for line in lines)


def test_draft_without_music_is_passthrough() -> None:
    assert AudioMixer.build_mix_graph("tts", None, RenderProfile.DRAFT) == ([], "tts")


@pytest.mark.parametrize("profile", list(RenderProfile))
@pytest.mark.parametrize("bg", [None, "bg"])
def test_every_profile_produces_valid_graph(
    profile: RenderProfile, bg: str | None
) -> None:
    lines, out = AudioMixer.build_mix_graph("tts", bg, profile)

    GraphValidator.validate_graph(lines, [f"[{out}]"])
