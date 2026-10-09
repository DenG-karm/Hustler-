"""AssDocument: zaman biçimi ve nihai .ass metni."""

import pytest

from services.core.hustler.generators.subtitle_generator import (
    AssDocument,
    SubtitleStyle,
)
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0, "0:00:00.00"),
        (10, "0:00:00.01"),
        (1900, "0:00:01.90"),
        (999, "0:00:01.00"),  # yuvarlama taşması
        (59_999, "0:01:00.00"),
        (3_599_999, "1:00:00.00"),
        (3_600_000, "1:00:00.00"),
        (3_723_450, "1:02:03.45"),
        (36_000_000, "10:00:00.00"),
    ],
)
def test_ms_to_ass_time(ms: int, expected: str) -> None:
    assert AssDocument.ms_to_ass_time(ms) == expected


@pytest.mark.xfail(
    strict=True, reason="BULGU: negatif ms reddedilmiyor, bozuk ASS zamanı üretiliyor"
)
def test_negative_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError):
        AssDocument.ms_to_ass_time(-500)


def _default_style() -> SubtitleStyle:
    return SubtitleStyle(
        font_name="Arial",
        font_size=90,
        primary_color="&H00FFFFFF&",
        highlight_color="&H0000FFFF&",
        alignment=5,
        margin_v=50,
    )


def test_generate_emits_header_style_and_exact_dialogue_lines() -> None:
    words = [
        WordTiming(word="Merhaba", start_ms=0, end_ms=500),
        WordTiming(word="dünya", start_ms=500, end_ms=1900),
    ]

    doc = AssDocument.generate(words, _default_style())

    lines = doc.split("\n")
    assert lines[0] == "[Script Info]"
    assert "PlayResX: 1080" in lines and "PlayResY: 1920" in lines
    style = next(ln for ln in lines if ln.startswith("Style: "))
    assert style.startswith("Style: Default,Arial,90,&H00FFFFFF&,")
    assert ",5,10,10,50,1" in style
    dialogues = [ln for ln in lines if ln.startswith("Dialogue:")]
    assert dialogues == [
        "Dialogue: 0,0:00:00.00,0:00:00.50,Default,,0,0,0,,{\\c&H0000FFFF&}Merhaba",
        "Dialogue: 0,0:00:00.50,0:00:01.90,Default,,0,0,0,,{\\c&H0000FFFF&}dünya",
    ]
    assert doc.endswith("\n")


def test_custom_style_values_are_embedded() -> None:
    style = SubtitleStyle(
        font_name="Impact",
        font_size=70,
        primary_color="&H00FFFFFF&",
        alignment=2,
        margin_v=120,
        highlight_color="&H000000FF&",
    )

    doc = AssDocument.generate([WordTiming(word="x", start_ms=0, end_ms=10)], style)

    assert "Style: Default,Impact,70," in doc
    assert ",2,10,10,120,1" in doc
    assert "{\\c&H000000FF&}x" in doc


def test_no_words_yields_header_only_without_dialogue() -> None:
    doc = AssDocument.generate([], _default_style())

    assert "Dialogue:" not in doc
    assert "[Events]" in doc


def test_ten_thousand_words_are_all_emitted_quickly() -> None:
    words = [
        WordTiming(word=f"w{i}", start_ms=i * 10, end_ms=i * 10 + 9)
        for i in range(10_000)
    ]

    doc = AssDocument.generate(words, _default_style())

    assert doc.count("Dialogue:") == 10_000
