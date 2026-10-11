from typing import Any, Mapping, Sequence

from services.core.hustler.infrastructure.timestamp_normalizer import (
    TimestampNormalizer,
    WordTiming,
)


class AlignmentError(ValueError):
    """TTS karakter hizalaması eksik, tutarsız veya bozuk."""


def characters_to_words(
    characters: Sequence[str],
    starts: Sequence[float],
    ends: Sequence[float],
) -> list[dict[str, Any]]:
    """
    Karakter bazlı zamanlamayı (saniye) kelime bazlı ham zamanlamaya çevirir.
    Kelime = boşlukla ayrılmış ardışık karakterler (noktalama kelimeye bağlı kalır).
    Çıktı, TimestampNormalizer.normalize_timings girdisiyle uyumludur.
    """
    if not (len(characters) == len(starts) == len(ends)):
        raise AlignmentError(
            f"Hizalama dizileri eşit uzunlukta değil: "
            f"characters={len(characters)} starts={len(starts)} ends={len(ends)}"
        )

    words: list[dict[str, Any]] = []
    buffer: list[str] = []
    word_start = 0.0
    word_end = 0.0

    for ch, start, end in zip(characters, starts, ends):
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise AlignmentError(f"Sayısal olmayan zaman değeri: {ch!r} ({start!r}-{end!r})")
        if ch.isspace():
            if buffer:
                words.append({"word": "".join(buffer), "start": word_start, "end": word_end})
                buffer = []
            continue
        if not buffer:
            word_start = float(start)
        word_end = float(end)
        buffer.append(ch)

    if buffer:
        words.append({"word": "".join(buffer), "start": word_start, "end": word_end})
    return words


def alignment_to_word_timings(alignment: Mapping[str, Any] | None) -> list[WordTiming]:
    """ElevenLabs `alignment` nesnesini normalize edilmiş WordTiming listesine çevirir."""
    if not alignment:
        raise AlignmentError("Yanıtta alignment verisi yok")
    try:
        raw = characters_to_words(
            alignment["characters"],
            alignment["character_start_times_seconds"],
            alignment["character_end_times_seconds"],
        )
    except (KeyError, TypeError) as exc:
        raise AlignmentError(f"Alignment şeması bozuk: {type(exc).__name__}: {exc}") from exc

    timings = TimestampNormalizer.normalize_timings(raw)
    if not timings:
        raise AlignmentError("Alignment hiç kelime içermiyor")
    return timings
