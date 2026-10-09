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
