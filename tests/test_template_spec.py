"""TemplateSpec: şablon sözleşmesi sınır doğrulamaları."""

import pytest
from pydantic import ValidationError

from services.core.hustler.domain.models.template import TemplateSpec

RENDER = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "bg_color": "#000000",
    "safe_zone": {
        "margin_top": 100,
        "margin_bottom": 100,
        "margin_left": 50,
        "margin_right": 50,
    },
}


def _data(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Motivasyon Shorts Şablonu",
        "target_duration_sec": 60,
        "max_scenes": 5,
        "allowed_tones": ["ilham verici", "heyecanlı", "didaktik"],
        "render_config": dict(RENDER),
    }
    base.update(overrides)
    return base


def test_valid_template_is_parsed_into_typed_model() -> None:
    spec = TemplateSpec.model_validate(_data())

    assert spec.name == "Motivasyon Shorts Şablonu"
    assert spec.target_duration_sec == 60
    assert spec.max_scenes == 5
    assert len(spec.allowed_tones) == 3
    assert spec.render_config.width == 1080


def test_template_violating_every_rule_reports_four_errors() -> None:
    bad = _data(name="Ab", target_duration_sec=5, max_scenes=15, allowed_tones=[])

    with pytest.raises(ValidationError) as info:
        TemplateSpec.model_validate(bad)

    fields = {err["loc"][0] for err in info.value.errors()}
    assert info.value.error_count() == 4
    assert fields == {"name", "target_duration_sec", "max_scenes", "allowed_tones"}


@pytest.mark.parametrize(
    ("field", "ok", "bad"),
    [
        ("target_duration_sec", 15, 14),
        ("target_duration_sec", 180, 181),
        ("max_scenes", 1, 0),
        ("max_scenes", 10, 11),
    ],
)
def test_numeric_boundaries_accept_edge_and_reject_just_outside(
    field: str, ok: int, bad: int
) -> None:
    assert getattr(TemplateSpec.model_validate(_data(**{field: ok})), field) == ok
    with pytest.raises(ValidationError):
        TemplateSpec.model_validate(_data(**{field: bad}))


def test_missing_render_config_is_rejected() -> None:
    data = _data()
    del data["render_config"]

    with pytest.raises(ValidationError) as info:
        TemplateSpec.model_validate(data)

    assert info.value.errors()[0]["loc"] == ("render_config",)


def test_invalid_nested_render_config_is_rejected() -> None:
    with pytest.raises(ValidationError) as info:
        TemplateSpec.model_validate(_data(render_config={**RENDER, "fps": 60}))

    assert info.value.errors()[0]["loc"] == ("render_config", "fps")
