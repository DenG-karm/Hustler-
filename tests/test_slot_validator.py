"""M6 K-610: SlotValidator Birim ve Entegrasyon Testleri.

Test Edilen Kriterler:
1. Zorunlu dosya eksikliğinde MissingAssetSlotError fırlatılması.
2. Video slotuna ses dosyası gönderildiğinde AssetTypeError fırlatılması.
3. 16:9 yatay videonun 9:16 şablona girdiğinde RatioMismatchWarning üretmesi ve
   filtre zincirine (filter_chain) kurtarma stratejisine göre crop veya pad eklenmesi.
"""

from pathlib import Path
import pytest

from services.core.hustler.domain.models.template import (
    AssetType,
    RecoveryStrategy,
    RenderConfig,
    SafeZone,
    SlotSpec,
    TemplateSpec,
)
from services.core.hustler.render.test_profile import (
    generate_synthetic_audio_asset,
    generate_synthetic_video_asset,
)
from services.core.hustler.validation.slot_validator import (
    AssetTypeError,
    MissingAssetSlotError,
    RatioMismatchWarning,
    SlotValidator,
)


@pytest.fixture
def vertical_template() -> TemplateSpec:
    """Standart 1080x1920 (9:16) Dikey Shorts Şablonu."""
    zone = SafeZone(margin_top=100, margin_bottom=100, margin_left=50, margin_right=50)
    return TemplateSpec(
        name="Shorts Şablonu",
        target_duration_sec=30,
        max_scenes=2,
        allowed_tones=["ciddi"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=zone,
        ),
        recovery_strategy=RecoveryStrategy.CROP,
    )


def test_missing_required_slot_raises_error(
    vertical_template: TemplateSpec,
    tmp_path: Path,
) -> None:
    """Zorunlu bir slot için dosya sağlanmadığında MissingAssetSlotError fırlatıldığını kanıtlar."""
    slots = [
        SlotSpec(slot_id="hero_video", expected_type=AssetType.VIDEO, required=True),
        SlotSpec(slot_id="bg_audio", expected_type=AssetType.AUDIO, required=True),
    ]
    validator = SlotValidator(vertical_template, slots=slots)

    # Ses var ama zorunlu hero_video eksik
    audio_file = generate_synthetic_audio_asset(tmp_path / "audio.mp3", duration_sec=1.0)
    asset_map = {"bg_audio": audio_file}

    with pytest.raises(MissingAssetSlotError, match="Zorunlu slot eksik: 'hero_video'"):
        validator.validate_slots(asset_map)


def test_type_mismatch_audio_in_video_slot_raises_error(
    vertical_template: TemplateSpec,
    tmp_path: Path,
) -> None:
    """Video slotuna ses dosyası gönderildiğinde AssetTypeError fırlatıldığını kanıtlar."""
    slots = [
        SlotSpec(slot_id="scene_0", expected_type=AssetType.VIDEO, required=True),
    ]
    validator = SlotValidator(vertical_template, slots=slots)

    # Ses dosyasını video slotuna eşle
    audio_file = generate_synthetic_audio_asset(tmp_path / "wrong_audio.mp3", duration_sec=1.0)

    with pytest.raises(AssetTypeError, match="Asset tip uyuşmazlığı: 'scene_0' slotu VIDEO bekliyor"):
        validator.validate_slots({"scene_0": audio_file})


def test_landscape_video_in_vertical_template_warns_and_applies_crop(
    vertical_template: TemplateSpec,
    tmp_path: Path,
) -> None:
    """16:9 yatay video 9:16 şablona girdiğinde uyarı verdiğini ve crop filtresi enjekte ettiğini doğrular."""
    # 16:9 (1280x720) yatay video üret
    landscape_video = generate_synthetic_video_asset(
        tmp_path / "landscape.mp4",
        duration_sec=1.0,
        width=1280,
        height=720,
    )

    slots = [
        SlotSpec(slot_id="scene_0", expected_type=AssetType.VIDEO, required=True),
    ]
    vertical_template.recovery_strategy = RecoveryStrategy.CROP
    validator = SlotValidator(vertical_template, slots=slots)

    # RatioMismatchWarning uyarısının fırlatıldığını doğrula
    with pytest.warns(RatioMismatchWarning, match="En-boy oranı uyuşmazlığı: 'scene_0'") as record:
        results = validator.validate_slots({"scene_0": landscape_video})

    assert len(record) == 1
    res = results["scene_0"]
    assert res.has_ratio_mismatch is True
    assert res.recovery_strategy_applied == RecoveryStrategy.CROP
    assert res.width == 1280
    assert res.height == 720

    # AST FilterChain içinde crop ve scale filtresi olduğunu ve stretch olmadığını doğrula
    assert res.filter_chain is not None
    filter_names = [f.name for f in res.filter_chain.filters]
    assert "scale" in filter_names
    assert "crop" in filter_names
    assert "setsar" in filter_names

    chain_str = res.filter_chain.to_string()
    assert "force_original_aspect_ratio=increase" in chain_str
    assert "crop=1080:1920" in chain_str
    assert "setsar=1" in chain_str


def test_landscape_video_in_vertical_template_warns_and_applies_pad(
    vertical_template: TemplateSpec,
    tmp_path: Path,
) -> None:
    """Kurtarma stratejisi PAD olduğunda filtre zincirine pad filtresi eklendiğini doğrular."""
    # 16:9 (1920x1080) yatay video üret
    landscape_video = generate_synthetic_video_asset(
        tmp_path / "landscape_1080p.mp4",
        duration_sec=1.0,
        width=1920,
        height=1080,
    )

    slots = [
        SlotSpec(slot_id="scene_0", expected_type=AssetType.VIDEO, required=True),
    ]
    vertical_template.recovery_strategy = RecoveryStrategy.PAD
    validator = SlotValidator(vertical_template, slots=slots)

    with pytest.warns(RatioMismatchWarning):
        results = validator.validate_slots({"scene_0": landscape_video})

    res = results["scene_0"]
    assert res.has_ratio_mismatch is True
    assert res.recovery_strategy_applied == RecoveryStrategy.PAD

    # AST FilterChain içinde pad filtresi olduğunu doğrula
    assert res.filter_chain is not None
    filter_names = [f.name for f in res.filter_chain.filters]
    assert "scale" in filter_names
    assert "pad" in filter_names
    assert "setsar" in filter_names

    chain_str = res.filter_chain.to_string()
    assert "force_original_aspect_ratio=decrease" in chain_str
    assert "pad=1080:1920:(1080-iw)/2:(1920-ih)/2" in chain_str


def test_matching_vertical_video_produces_no_warning(
    vertical_template: TemplateSpec,
    tmp_path: Path,
) -> None:
    """9:16 oranlı dikey video girdiğinde hiçbir uyarı verilmediğini doğrular."""
    # 9:16 (1080x1920) dikey video üret
    vertical_video = generate_synthetic_video_asset(
        tmp_path / "vertical_1080x1920.mp4",
        duration_sec=1.0,
        width=1080,
        height=1920,
    )

    slots = [
        SlotSpec(slot_id="scene_0", expected_type=AssetType.VIDEO, required=True),
    ]
    validator = SlotValidator(vertical_template, slots=slots)

    import warnings
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        results = validator.validate_slots({"scene_0": vertical_video})

    # Hiçbir RatioMismatchWarning olmamalı
    mismatch_warnings = [w for w in recorded if issubclass(w.category, RatioMismatchWarning)]
    assert len(mismatch_warnings) == 0

    res = results["scene_0"]
    assert res.has_ratio_mismatch is False
    assert res.recovery_strategy_applied is None
