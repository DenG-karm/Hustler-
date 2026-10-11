"""Karakter -> kelime hizalaması: saf mantık, ağ yok."""

from typing import Any

import pytest

from services.core.hustler.generators.subtitle_generator import AssDocument, SubtitleStyle
from services.core.hustler.infrastructure.word_alignment import (
    AlignmentError,
    alignment_to_word_timings,
    characters_to_words,
)


def _alignment(text: str, step: float = 0.1, start: float = 0.0) -> dict[str, Any]:
    chars = list(text)
    starts = [round(start + i * step, 3) for i in range(len(chars))]
    return {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": [round(s + step, 3) for s in starts],
    }


def test_words_take_first_char_start_and_last_char_end() -> None:
    a = _alignment("ab cd")
    words = characters_to_words(
        a["characters"], a["character_start_times_seconds"], a["character_end_times_seconds"]
    )

    assert words == [
        {"word": "ab", "start": 0.0, "end": 0.2},
        {"word": "cd", "start": 0.3, "end": 0.5},
    ]


def test_punctuation_stays_attached_and_turkish_chars_survive() -> None:
    timings = alignment_to_word_timings(_alignment("Şöyle, ğüzel!"))

    assert [t.word for t in timings] == ["Şöyle,", "ğüzel!"]
    assert timings[0].start_ms == 0
    assert timings[1].start_ms == 700


@pytest.mark.parametrize("text", ["a  b", "a \n b", "a\tb"])
def test_multiple_or_mixed_whitespace_never_creates_empty_words(text: str) -> None:
    timings = alignment_to_word_timings(_alignment(text))

    assert [t.word for t in timings] == ["a", "b"]


def test_leading_and_trailing_whitespace_is_ignored() -> None:
    timings = alignment_to_word_timings(_alignment("  hi  "))

    assert [t.word for t in timings] == ["hi"]
    assert timings[0].start_ms == 200


def test_timings_are_integer_ms_monotonic_and_non_overlapping() -> None:
    a = _alignment("bir iki üç dört", step=0.0731)
    timings = alignment_to_word_timings(a)

    assert all(isinstance(t.start_ms, int) and isinstance(t.end_ms, int) for t in timings)
    for cur, nxt in zip(timings, timings[1:]):
        assert cur.start_ms <= cur.end_ms <= nxt.start_ms


def test_overlapping_char_times_are_trimmed_by_existing_normalizer() -> None:
    a = {
        "characters": list("a b"),
        "character_start_times_seconds": [0.0, 0.2, 0.3],
        "character_end_times_seconds": [0.5, 0.25, 0.6],
    }
    timings = alignment_to_word_timings(a)

    assert timings[0].end_ms == timings[1].start_ms == 300


@pytest.mark.parametrize(
    "alignment",
    [
        None,
        {},
        {"characters": ["a"]},
        {"characters": ["a"], "character_start_times_seconds": [0.0]},
        {"characters": None, "character_start_times_seconds": [], "character_end_times_seconds": []},
    ],
)
def test_missing_or_malformed_alignment_raises(alignment: Any) -> None:
    with pytest.raises(AlignmentError):
        alignment_to_word_timings(alignment)


def test_length_mismatch_raises() -> None:
    with pytest.raises(AlignmentError, match="eşit uzunlukta"):
        characters_to_words(["a", "b"], [0.0], [0.1, 0.2])


def test_non_numeric_time_raises() -> None:
    with pytest.raises(AlignmentError, match="Sayısal olmayan"):
        characters_to_words(["a"], ["x"], [0.1])  # type: ignore[list-item]


def test_whitespace_only_alignment_raises() -> None:
    with pytest.raises(AlignmentError, match="hiç kelime"):
        alignment_to_word_timings(_alignment("   "))


def test_negative_char_time_is_rejected_by_normalizer() -> None:
    a = _alignment("ab")
    a["character_start_times_seconds"][0] = -0.5

    with pytest.raises(ValueError, match="Negatif"):
        alignment_to_word_timings(a)


def test_alignment_drives_ass_with_real_unequal_durations() -> None:
    # "a" kısa, "uzunkelime" uzun konuşulur; eşit dağıtım bunu yakalayamazdı.
    chars = list("a uzunkelime")
    timings = alignment_to_word_timings(
        {
            "characters": chars,
            "character_start_times_seconds": [round(i * 0.1, 3) for i in range(len(chars))],
            "character_end_times_seconds": [round((i + 1) * 0.1, 3) for i in range(len(chars))],
        }
    )
    ass = AssDocument.generate(timings, SubtitleStyle())
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]

    assert len(dialogues) == 2
    assert dialogues[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.10,")
    assert dialogues[1].startswith("Dialogue: 0,0:00:00.20,0:00:01.20,")
    assert dialogues[0].endswith("a") and dialogues[1].endswith("uzunkelime")
