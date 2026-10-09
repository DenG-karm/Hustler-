"""Python süreci aniden öldürülünce FFmpeg çocuğunun hayatta kalmaması gerekir (Job Object)."""

import asyncio
import ctypes
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.ffmpeg,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows"),
]

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_DRIVER = textwrap.dedent(
    """
    import asyncio, sys
    sys.path.insert(0, {root!r})
    from services.core.hustler.render.ffmpeg_runner import FFmpegRunner

    _real = asyncio.create_subprocess_exec

    async def _spy(*a, **k):
        proc = await _real(*a, **k)
        print("FFPID", proc.pid, flush=True)
        return proc

    asyncio.create_subprocess_exec = _spy

    async def main():
        runner = FFmpegRunner(asyncio.Semaphore(1), target_duration_sec=60.0, timeout_sec=120.0)
        cmd = ["ffmpeg", "-y", "-re", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=60",
               "-c:v", "libx264", "-f", "null", "-"]
        async for _ in runner.run(cmd, "orphan_probe.mp4"):
            pass

    asyncio.run(main())
    """
)


def _is_alive(pid: int) -> bool:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    return bool(ok) and code.value == _STILL_ACTIVE


def _force_kill(pid: int) -> None:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
    if handle:
        kernel32.TerminateProcess(handle, 1)
        kernel32.CloseHandle(handle)


async def test_ffmpeg_child_dies_when_python_parent_is_killed(tmp_path: Path) -> None:
    script = tmp_path / "driver.py"
    script.write_text(_DRIVER.format(root=str(_PROJECT_ROOT)), encoding="utf-8")
    parent = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=str(tmp_path),
    )
    assert parent.stdout is not None
    ffmpeg_pid = 0
    try:
        line = await asyncio.wait_for(parent.stdout.readline(), timeout=20)
        assert line.startswith(b"FFPID"), line
        ffmpeg_pid = int(line.split()[1])
        await asyncio.sleep(1.0)
        assert _is_alive(ffmpeg_pid), "ffmpeg başlamadı"

        parent.kill()  # ani ölüm: finally/cancel yolu çalışmaz
        await parent.wait()

        deadline = time.monotonic() + 5.0
        while _is_alive(ffmpeg_pid) and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        orphaned = _is_alive(ffmpeg_pid)
    finally:
        if ffmpeg_pid:
            _force_kill(ffmpeg_pid)

    # BULGU: üretimde Job Object (KILL_ON_JOB_CLOSE) yok; test üretim kodu düzelene dek KIRMIZI
    assert not orphaned, f"ffmpeg pid={ffmpeg_pid} ebeveyn öldükten sonra yetim kaldı"
