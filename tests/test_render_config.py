"""RenderConfig: sadece 1080x1920 @ 30 FPS dikey format kabul edilir."""

import pytest
from pydantic import ValidationError

from services.core.hustler.domain.models.template import RenderConfig, SafeZone

SAFE_ZONE = {"margin_top": 200, "margin_bottom": 250, "margin_left": 50, "margin_right": 50}


def _data(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "bg_color": "#000000",
        "safe_zone": dict(SAFE_ZONE),
    }
    base.update(overrides)
    return base


def test_valid_config_is_converted_to_typed_model() -> None:
    cfg = RenderConfig.model_validate(_data())

    assert isinstance(cfg, RenderConfig)
    assert isinstance(cfg.safe_zone, SafeZone)
    assert (cfg.width, cfg.height, cfg.fps) == (1080, 1920, 30)
    assert cfg.safe_zone.model_dump() == SAFE_ZONE


def test_landscape_60fps_config_reports_all_three_violations() -> None:
    with pytest.raises(ValidationError) as info:
        RenderConfig.model_validate(_data(width=1920, height=1080, fps=60))

    fields = {err["loc"][0] for err in info.value.errors()}
    assert info.value.error_count() == 3
    assert fields == {"width", "height", "fps"}


@pytest.mark.parametrize(
    ("field", "value"), [("width", 720), ("height", 1280), ("fps", 24)]
)
def test_single_invalid_dimension_is_rejected(field: str, value: int) -> None:
    with pytest.raises(ValidationError) as info:
        RenderConfig.model_validate(_data(**{field: value}))

    assert [err["loc"][0] for err in info.value.errors()] == [field]


def test_missing_safe_zone_is_rejected() -> None:
    data = _data()
    del data["safe_zone"]

    with pytest.raises(ValidationError) as info:
        RenderConfig.model_validate(data)

    assert info.value.errors()[0]["type"] == "missing"
