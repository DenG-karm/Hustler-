"""Job Object bağlama: gerçek Win32 çağrıları (Windows) + platform/hata yolları."""

import asyncio
import sys

import pytest

from services.core.hustler.render import job_object


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object yalnızca Windows")
async def test_bind_real_child_process_succeeds_and_job_is_reused() -> None:
    procs = [
        await asyncio.create_subprocess_exec(
            sys.executable, "-c", "import time; time.sleep(30)"
        )
        for _ in range(2)
    ]
    try:
        results = [job_object.bind_pid_to_kill_on_close_job(p.pid) for p in procs]
        assert results == [True, True]
        assert job_object._job_handle is not None
    finally:
        for p in procs:
            p.kill()
            await p.wait()


@pytest.mark.skipif(sys.platform != "win32", reason="Job Object yalnızca Windows")
def test_bind_nonexistent_pid_returns_false_without_raising() -> None:
    assert job_object.bind_pid_to_kill_on_close_job(0x7FFFFFF0) is False


def test_bind_is_noop_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")

    assert job_object.bind_pid_to_kill_on_close_job(1234) is False
