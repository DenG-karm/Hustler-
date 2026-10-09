"""TimestampNormalizer: saniye->ms, ters zaman ve çakışma düzeltmesi."""

import pytest

from services.core.hustler.infrastructure.timestamp_normalizer import (
    TimestampNormalizer,
    WordTiming,
)


def _raw(word: str, start: object, end: object) -> dict[str, object]:
    return {"word": word, "start": start, "end": end}


def test_seconds_are_converted_to_integer_milliseconds_and_words_stripped() -> None:
    out = TimestampNormalizer.normalize_timings([_raw(" merhaba ", 0.5, 1.25)])

    assert out == [WordTiming(word="merhaba", start_ms=500, end_ms=1250)]
    assert isinstance(out[0].start_ms, int)


def test_overlap_trims_previous_word_to_next_start() -> None:
    out = TimestampNormalizer.normalize_timings(
        [_raw("a", 0.0, 0.5), _raw("b", 0.4, 0.9)]
    )

    assert [(w.start_ms, w.end_ms) for w in out] == [(0, 400), (400, 900)]


def test_reversed_range_is_collapsed_to_zero_length() -> None:
    out = TimestampNormalizer.normalize_timings([_raw("a", 2.0, 1.0)])

    assert (out[0].start_ms, out[0].end_ms) == (2000, 2000)


@pytest.mark.parametrize("raw", [[], None])
def test_empty_input_returns_empty_list(raw: list[dict[str, object]] | None) -> None:
    assert TimestampNormalizer.normalize_timings(raw or []) == []


def test_missing_keys_default_to_empty_word_and_zero_time() -> None:
    out = TimestampNormalizer.normalize_timings([{}])

    assert out == [WordTiming(word="", start_ms=0, end_ms=0)]


@pytest.mark.parametrize(
    ("bad", "error"), [("abc", ValueError), (None, TypeError), ([1], TypeError)]
)
def test_non_numeric_timestamp_raises(bad: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        TimestampNormalizer.normalize_timings([_raw("a", bad, 1)])


def test_output_never_overlaps_for_chaotic_input() -> None:
    raw = [_raw(f"w{i}", i * 0.1, i * 0.1 + 0.35) for i in range(50)]

    out = TimestampNormalizer.normalize_timings(raw)

    assert all(a.end_ms <= b.start_ms for a, b in zip(out, out[1:]))
    assert all(w.start_ms <= w.end_ms for w in out)


def test_negative_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError):
        TimestampNormalizer.normalize_timings([_raw("a", -1.0, 0.5)])
