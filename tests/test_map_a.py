"""Map A: saf fonksiyon, deterministik filtreler."""

import pytest

from services.core.hustler.domain.map_a import (
    MAX_WPM,
    MIN_WORD_COUNT,
    MIN_WPM,
    MapAResult,
    analyze_transcript,
)

NORMAL_TEXT = (
    "Videoma hoşgeldiniz. Bu içeriği beğendiyseniz kanalıma abone ol demeyi "
    "unutmayın. Ayrıca tüm detaylar için link bio'da yer alıyor. Şimdi ana "
    "konuya geçelim. Burada konuşmaya ve kelime sayısını doldurmaya devam "
    "ediyorum. "
) * 4


def test_short_text_is_rejected_for_low_word_count() -> None:
    res = analyze_transcript("Merhaba arkadaşlar. Bugün çok güzel. " * 4, 60)

    assert isinstance(res, MapAResult)
    assert res.is_accepted is False
    assert res.word_count < MIN_WORD_COUNT
    assert res.rejection_reason is not None
    assert "yetersiz" in res.rejection_reason


def test_normal_text_with_cta_is_accepted() -> None:
    res = analyze_transcript(NORMAL_TEXT, 60)

    assert res.is_accepted is True
    assert res.rejection_reason is None
    assert res.has_cta is True
    assert MIN_WPM <= res.wpm <= MAX_WPM
    assert res.word_count >= MIN_WORD_COUNT


def test_machine_speed_text_is_rejected_for_high_wpm() -> None:
    res = analyze_transcript("kelime " * 300, 60)

    assert res.is_accepted is False
    assert res.wpm == 300
    assert res.wpm > MAX_WPM
    assert res.rejection_reason is not None
    assert "yüksek" in res.rejection_reason


def test_slow_speech_is_rejected_for_low_wpm() -> None:
    res = analyze_transcript("kelime " * 60, 60 * 5)

    assert res.is_accepted is False
    assert res.wpm < MIN_WPM
    assert res.rejection_reason is not None
    assert "düşük" in res.rejection_reason


def test_text_without_cta_phrase_reports_no_cta() -> None:
    res = analyze_transcript("kelime " * 100, 60)

    assert res.is_accepted is True
    assert res.has_cta is False


@pytest.mark.parametrize(
    ("text", "duration"), [("", 60), ("kelime " * 100, 0), ("kelime", -5)]
)
def test_empty_text_or_invalid_duration_is_rejected_without_crash(
    text: str, duration: int
) -> None:
    res = analyze_transcript(text, duration)

    assert res.is_accepted is False
    assert res.word_count == 0
    assert res.wpm == 0
    assert res.rejection_reason == "Boş metin veya geçersiz süre"
