"""ScriptDoc: JSON şema sözleşmesi ve sınır doğrulamaları."""

import pytest
from pydantic import ValidationError

from services.core.hustler.domain.models.script import ScriptDoc

GOOD = {
    "hook": "Sadece 3 adımda finansal özgürlüğün sırrını keşfet!",
    "body": ["İlk adım.", "İkinci adım.", "Son adım."],
    "cta": "Daha fazlası için profilimdeki linke tıkla!",
    "estimated_duration": 45,
}


def test_valid_script_is_parsed_into_typed_model() -> None:
    doc = ScriptDoc.model_validate(GOOD)

    assert isinstance(doc, ScriptDoc)
    assert len(doc.body) == 3
    assert doc.estimated_duration == 45


def test_invalid_script_reports_hook_cta_and_duration_violations() -> None:
    bad = {"hook": "x" * 151, "body": ["a"], "estimated_duration": -5}

    with pytest.raises(ValidationError) as info:
        ScriptDoc.model_validate(bad)

    types_by_field = {err["loc"][0]: err["type"] for err in info.value.errors()}
    assert info.value.error_count() == 3
    assert types_by_field == {
        "hook": "string_too_long",
        "cta": "missing",
        "estimated_duration": "greater_than",
    }


def test_hook_of_exactly_150_chars_is_accepted_and_151_rejected() -> None:
    assert len(ScriptDoc.model_validate({**GOOD, "hook": "x" * 150}).hook) == 150
    with pytest.raises(ValidationError):
        ScriptDoc.model_validate({**GOOD, "hook": "x" * 151})


def test_empty_body_is_rejected() -> None:
    with pytest.raises(ValidationError) as info:
        ScriptDoc.model_validate({**GOOD, "body": []})

    assert info.value.errors()[0]["loc"] == ("body",)


def test_zero_duration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScriptDoc.model_validate({**GOOD, "estimated_duration": 0})


def test_llm_schema_exposes_required_fields_and_limits() -> None:
    schema = ScriptDoc.get_llm_schema()

    assert isinstance(schema, dict)
    assert set(schema["required"]) == {"hook", "body", "cta", "estimated_duration"}
    assert schema["properties"]["hook"]["maxLength"] == 150
    assert schema["properties"]["cta"]["maxLength"] == 100
    assert schema["properties"]["body"]["minItems"] == 1
