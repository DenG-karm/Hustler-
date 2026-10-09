"""hardware.py: gerçek mantık; yalnızca nvidia-smi alt süreci ve (benchmark için) saat sahte."""

import asyncio
from collections.abc import Callable, Coroutine
from types import SimpleNamespace

import pytest

from services.core.hustler import db as db_module
from services.core.hustler.infrastructure import hardware


class FakeProc:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"", b""


def _spawn(
    proc: FakeProc | Exception,
) -> Callable[..., Coroutine[object, object, FakeProc]]:
    async def fake(*args: object, **kwargs: object) -> FakeProc:
        assert args == ("nvidia-smi",)
        if isinstance(proc, Exception):
            raise proc
        return proc

    return fake


@pytest.mark.parametrize(
    ("proc", "expected"),
    [
        (FakeProc(0), True),
        (FakeProc(9), False),
        (FileNotFoundError(), False),
        (PermissionError(), False),
        (OSError("boom"), False),
    ],
)
async def test_detect_cuda(
    monkeypatch: pytest.MonkeyPatch, proc: FakeProc | Exception, expected: bool
) -> None:
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spawn(proc))

    assert await hardware.detect_cuda() is expected


async def test_detect_cuda_timeout_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spawn(FakeProc(0)))

    async def timeout(
        coro: Coroutine[object, object, object], timeout: float
    ) -> object:
        coro.close()
        assert timeout == 2.0
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", timeout)

    assert await hardware.detect_cuda() is False


@pytest.mark.parametrize(
    ("elapsed", "score"),
    [(0.2, 1.0), (0.1, 2.0), (0.4, 0.5), (0.0, 200.0)],
)
def test_rtf_score_formula(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, score: float
) -> None:
    ticks = iter([10.0, 10.0 + elapsed])
    monkeypatch.setattr(
        hardware, "time", SimpleNamespace(perf_counter=lambda: next(ticks))
    )

    assert hardware.run_rtf_benchmark() == score


def test_real_benchmark_returns_positive_float() -> None:
    result = hardware.run_rtf_benchmark()

    assert isinstance(result, float)
    assert result > 0


async def test_measure_and_save_profile_persists_row_and_upserts(
    monkeypatch: pytest.MonkeyPatch, db: db_module.Database
) -> None:
    async def cuda() -> bool:
        return True

    monkeypatch.setattr(hardware, "detect_cuda", cuda)
    await hardware.init_hardware_profile(db)

    first = await hardware.measure_and_save_profile(db)
    second = await hardware.measure_and_save_profile(db)
    await db.trigger_maintenance()

    conn = await db.get_reader()
    async with conn.execute(
        "SELECT id, has_cuda, rtf_score FROM hardware_profile"
    ) as cur:
        rows = list(await cur.fetchall())
    await conn.close()
    assert first["has_cuda"] is True
    assert len(rows) == 1
    assert (rows[0][0], rows[0][1]) == (1, 1)
    assert rows[0][2] == second["rtf_score"]


async def test_profile_table_rejects_second_row(db: db_module.Database) -> None:
    await hardware.init_hardware_profile(db)
    await db.execute_write("INSERT INTO hardware_profile VALUES (1, 0, 1.0, 0)")

    with pytest.raises(Exception, match="CHECK|constraint"):
        await db.execute_write("INSERT INTO hardware_profile VALUES (2, 0, 1.0, 0)")


class _FfmpegFake:
    """ffmpeg alt s?recini sahteler: -encoders listesi ve hangi encoder'?n ba?lat?labildi?i."""

    def __init__(self, listed: str, working: set[str]) -> None:
        self.listed = listed
        self.working = working
        self.probed: list[str] = []

    def spawn(self, *args: object, **kwargs: object) -> object:
        argv = [str(a) for a in args]
        listing = self.listed
        if "-encoders" in argv:
            code = 0
        else:
            encoder = argv[argv.index("-c:v") + 1]
            self.probed.append(encoder)
            code = 0 if encoder in self.working else 1
            listing = ""

        class Proc:
            returncode = code

            async def communicate(self) -> tuple[bytes, None]:
                return listing.encode(), None

        async def make() -> Proc:
            return Proc()

        return make()


@pytest.mark.parametrize(
    ("listed", "working", "expected", "probed"),
    [
        (" V....D h264_nvenc\n V....D h264_amf\n", {"h264_nvenc", "h264_amf"}, "h264_nvenc", ["h264_nvenc"]),
        (" V....D h264_nvenc\n V....D h264_amf\n", {"h264_amf"}, "h264_amf", ["h264_nvenc", "h264_amf"]),
        (" V....D h264_nvenc\n", set(), "libx264", ["h264_nvenc"]),
        (" V....D libx264\n", {"h264_nvenc"}, "libx264", []),
    ],
)
async def test_select_video_encoder_prefers_working_hardware(
    monkeypatch: pytest.MonkeyPatch,
    listed: str,
    working: set[str],
    expected: str,
    probed: list[str],
) -> None:
    fake = _FfmpegFake(listed, working)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake.spawn)

    assert await hardware.select_video_encoder() == expected
    assert fake.probed == probed


async def test_select_video_encoder_falls_back_when_ffmpeg_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)

    assert await hardware.select_video_encoder() == "libx264"


async def test_hung_encoder_probe_is_killed_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[bool] = []

    class HungProc:
        returncode: int | None = None

        async def communicate(self) -> tuple[bytes, None]:
            await asyncio.sleep(60)
            return b"", None

        def kill(self) -> None:
            killed.append(True)

        async def wait(self) -> int:
            return -9

    code, text = await _run_with(monkeypatch, HungProc(), timeout=0.05)

    assert (code, text) == (-1, "timeout")
    assert killed == [True]


async def _run_with(
    monkeypatch: pytest.MonkeyPatch, proc: object, timeout: float
) -> tuple[int, str]:
    async def fake(*args: object, **kwargs: object) -> object:
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake)
    return await hardware._run_ffmpeg(["-encoders"], timeout=timeout)
