"""AudioCache gerçek disk mantığı (tmp_path); yalnızca TTS callback'i sahte."""

import hashlib
from pathlib import Path

import pytest

from services.core.hustler.infrastructure.audio_cache import AudioCache


class Recorder:
    def __init__(self, write: bool = True) -> None:
        self.paths: list[str] = []
        self.write = write

    async def __call__(self, output_path: str) -> None:
        self.paths.append(output_path)
        if self.write:
            Path(output_path).write_bytes(b"MP3")


def test_cache_dir_is_created(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"

    AudioCache(str(target))

    assert target.is_dir()


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Merhaba", "  merhaba  ", True),
        ("MERHABA", "merhaba", True),
        ("merhaba", "merhaba!", False),
    ],
)
def test_key_normalization(tmp_path: Path, a: str, b: str, same: bool) -> None:
    cache = AudioCache(str(tmp_path))

    assert (
        cache._generate_cache_key(a, "v") == cache._generate_cache_key(b, "v")
    ) is same


def test_key_is_exact_sha256_and_voice_sensitive(tmp_path: Path) -> None:
    cache = AudioCache(str(tmp_path))

    assert (
        cache._generate_cache_key(" Hi ", "v1")
        == hashlib.sha256(b"v1:::hi").hexdigest()
    )
    assert cache._generate_cache_key("hi", "v1") != cache._generate_cache_key(
        "hi", "v2"
    )


async def test_miss_calls_callback_once_then_hit_skips_it(tmp_path: Path) -> None:
    cache = AudioCache(str(tmp_path))
    cb = Recorder()

    first = await cache.get_or_fetch("selam", "v", cb)
    second = await cache.get_or_fetch("SELAM", "v", cb)

    assert first == second
    assert first.endswith(".mp3")
    assert Path(first).read_bytes() == b"MP3"
    assert cb.paths == [first]


async def test_callback_that_creates_no_file_raises(tmp_path: Path) -> None:
    cache = AudioCache(str(tmp_path))

    with pytest.raises(RuntimeError, match="fiziksel olarak oluşturamadı"):
        await cache.get_or_fetch("x", "v", Recorder(write=False))


async def test_callback_exception_propagates_and_nothing_is_cached(
    tmp_path: Path,
) -> None:
    cache = AudioCache(str(tmp_path))

    async def failing(_: str) -> None:
        raise ConnectionError("tts down")

    with pytest.raises(ConnectionError):
        await cache.get_or_fetch("x", "v", failing)

    assert list(tmp_path.iterdir()) == []


async def test_10k_char_text_still_produces_fixed_length_filename(
    tmp_path: Path,
) -> None:
    cache = AudioCache(str(tmp_path))

    path = await cache.get_or_fetch("a" * 10_000, "v", Recorder())

    assert len(Path(path).stem) == 64
