"""logging.setup_logging ve contracts.models.VideoRecord."""

import json
import logging
from collections.abc import Iterator

import pytest
import structlog
from pydantic import ValidationError

from services.core.hustler.contracts.models import VideoRecord
from services.core.hustler.logging import run_id_ctx, setup_logging


@pytest.fixture(autouse=True)
def _restore_structlog() -> Iterator[None]:
    yield
    structlog.reset_defaults()


def test_json_mode_emits_parsable_record_with_run_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    setup_logging(is_dev=False)
    token = run_id_ctx.set("run-42")
    try:
        structlog.get_logger("unit").info("olay", sayi=7)
    finally:
        run_id_ctx.reset(token)

    record = json.loads(caplog.records[-1].getMessage())
    assert record["event"] == "olay"
    assert record["sayi"] == 7
    assert record["level"] == "info"
    assert record["logger"] == "unit"
    assert record["run_id"] == "run-42"
    assert record["timestamp"].count("-") >= 2 and "T" in record["timestamp"]


def test_run_id_is_omitted_when_context_empty(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    setup_logging(is_dev=False)

    structlog.get_logger("unit").info("olay")

    assert "run_id" not in json.loads(caplog.records[-1].getMessage())


def test_dev_mode_is_not_json_but_contains_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    setup_logging(is_dev=True)

    structlog.get_logger("unit").info("gelistirme", k="v")

    msg = caplog.records[-1].getMessage()
    assert "gelistirme" in msg and "k" in msg
    with pytest.raises(json.JSONDecodeError):
        json.loads(msg)


def test_video_record_valid() -> None:
    v = VideoRecord(id="a", title="T", duration=0)

    assert v.model_dump() == {"id": "a", "title": "T", "duration": 0}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "a", "title": "T"},
        {"id": "a", "title": "T", "duration": "çok uzun"},
        {"id": None, "title": "T", "duration": 1},
        {"id": "a", "title": ["x"], "duration": 1},
    ],
)
def test_video_record_rejects_invalid_payload(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        VideoRecord.model_validate(payload)
