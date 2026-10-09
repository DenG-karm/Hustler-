import os
import sys
import asyncio
import time
import pytest
import ctypes
from typing import Any, AsyncGenerator

from services.core.hustler.render.ffmpeg_runner import (
    FFmpegRunner, RenderProgress, RenderComplete, RenderTimeout, RenderStalled, RenderFailed
)

pytestmark = pytest.mark.ffmpeg

def is_pid_alive(pid: int) -> bool:
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.windll.kernel32
    h_process = kernel32.OpenProcess(0x1000, False, pid)
    if not h_process:
        return False
    exit_code = ctypes.c_ulong()
    success = kernel32.GetExitCodeProcess(h_process, ctypes.byref(exit_code))
    kernel32.CloseHandle(h_process)
    if not success:
        return False
    return exit_code.value == 259

@pytest.fixture
def cpu_budget() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)

@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_a_normal_render(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
        "-c:v", "libx264", "-preset", "ultrafast",
        "dummy_output.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=1.0, timeout_sec=10.0)
    
    last_prog = -1.0
    completed = False
    
    async for event in runner.run(cmd, "dummy_output.mp4"):
        if isinstance(event, RenderProgress):
            assert event.progress >= last_prog, "İlerleme monoton değil!"
            last_prog = event.progress
        elif isinstance(event, RenderComplete):
            completed = True
            
    assert completed, "RenderComplete fırlatılmadı."
    assert last_prog == 100.0, "Son progress 100 değil."
    assert os.path.exists("dummy_output.mp4"), "Çıktı dosyası yok."
    assert not os.path.exists("dummy_output.mp4.part"), ".part dosyası kalmış."
    os.remove("dummy_output.mp4")

async def _consume_all(gen: AsyncGenerator[Any, None]) -> None:
    async for _ in gen:
        pass

@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_b_cancel_kill_and_budget(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-re", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "dummy_cancel.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=10.0)
    
    agen = runner.run(cmd, "dummy_cancel.mp4")
    # Tüketiciyi başlatıyoruz
    task = asyncio.create_task(_consume_all(agen))
    
    await asyncio.sleep(1.0)
    # PID bulmak için private olan _kill_process methodunu sömürmüyoruz,
    # generator içindeki local değişkene erişemeyiz. Ama os.path.exists('dummy_cancel.mp4.part') true.
    # PID'i bulmanın en iyi yolu ffmpeg adıyla aramaktır, fakat test b PID mesajı istiyor.
    # Biz runner içinde süreç id'sini dışarı sızdırmıyoruz. 
    # Fakat _consume_all ile süreci iptal ettiğimizde iptal oluyor.
    
    # PID kanıtı için: task.cancel() öncesi süreç çalışıyor mu? (Runner objesine pid ekleyemem, public imzayı bozmamak için)
    # Neyse, sys.executable (psutil benzeri) yerine WMI veya subprocess ile PID'leri listeleyelim:
    import subprocess
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq ffmpeg.exe" /NH', shell=True).decode('utf-8', errors='ignore')
    pid = -1
    for line in out.splitlines():
        if "ffmpeg.exe" in line:
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                pid = int(parts[1])
                break
                
    alive_before = is_pid_alive(pid) if pid != -1 else False
    
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
        
    await asyncio.sleep(0.5)
    alive_after = is_pid_alive(pid) if pid != -1 else False
    budget_free = not cpu_budget.locked()
    part_exists = os.path.exists("dummy_cancel.mp4.part")
    
    print(f"pid {pid} iptal öncesi canlı={alive_before}, sonrası canlı={alive_after}; CpuBudget serbest={budget_free}; .part yok={not part_exists}")
    
    assert alive_before, "İptal öncesi canlı olmalıydı"
    assert not alive_after, "İptal sonrası süreç ölmemiş!"
    assert budget_free, "CpuBudget serbest kalmadı!"
    assert not part_exists, ".part dosyası silinmedi!"

@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_c_timeout(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-re", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "dummy_timeout.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=1.0)
    
    with pytest.raises(RenderTimeout):
        async for _ in runner.run(cmd, "dummy_timeout.mp4"):
            pass
            
    assert not cpu_budget.locked()

@pytest.mark.asyncio
async def test_d_stall_watchdog(cpu_budget: asyncio.Semaphore) -> None:
    script_path = "mock_stall.py"
    with open(script_path, "w") as f:
        f.write("import sys, time\nprint('out_time_us=100000', flush=True)\ntime.sleep(5)\n")
                
    cmd = [sys.executable, script_path, "dummy_stall.mp4"]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=10.0, stall_timeout_sec=1.0)
    
    start_time = time.time()
    with pytest.raises(RenderStalled):
        async for _ in runner.run(cmd, "dummy_stall.mp4"):
            pass
            
    assert time.time() - start_time < 2.0
    os.remove(script_path)
    assert not cpu_budget.locked()

@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_e_invalid_filter_error(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
        "-filter_complex", "invalid_filter_name=1",
        "dummy_error.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=1.0)
    
    with pytest.raises(RenderFailed) as exc_info:
        async for _ in runner.run(cmd, "dummy_error.mp4"):
            pass
            
    assert "geçersiz" in str(exc_info.value).lower()
    assert not cpu_budget.locked()

@pytest.mark.asyncio
async def test_f_stderr_overflow(cpu_budget: asyncio.Semaphore) -> None:
    script_path = "mock_overflow.py"
    with open(script_path, "w") as f:
        f.write("import sys\nfor _ in range(10000):\n    sys.stderr.write('x' * 1000 + '\\n')\nsys.exit(1)\n")
                
    cmd = [sys.executable, script_path, "dummy_overflow.mp4"]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0)
    
    start = time.time()
    with pytest.raises(RenderFailed):
        async for _ in runner.run(cmd, "dummy_overflow.mp4"):
            pass
            
    duration = time.time() - start
    assert duration < 5.0, "Deadlock oldu, süreç zamanında kapanmadı!"
    os.remove(script_path)
    
@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_g_double_cancel(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-re", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=5",
        "-c:v", "libx264", "-preset", "ultrafast",
        "dummy_dcancel.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=10.0)
    
    task = asyncio.create_task(_consume_all(runner.run(cmd, "dummy_dcancel.mp4")))
    
    await asyncio.sleep(0.5)
    task.cancel()
    task.cancel() # Çifte iptal
    
    with pytest.raises(asyncio.CancelledError):
        await task
        
    assert not cpu_budget.locked()

@pytest.mark.asyncio
async def test_h_progress_parser(cpu_budget: asyncio.Semaphore) -> None:
    runner = FFmpegRunner(cpu_budget, target_duration_sec=1.0)
    
    assert runner._parse_progress("N/A", 0.0) is None
    assert runner._parse_progress("out_time_us=-100", 0.0) is None
    assert runner._parse_progress("out_time_us=500000", 0.0) == 50.0
    assert runner._parse_progress("frame=15", 0.0) is None
    
    runner2 = FFmpegRunner(cpu_budget, total_frames=30)
    assert runner2._parse_progress("frame=15", 0.0) == 50.0

@pytest.mark.asyncio
@pytest.mark.dryrun
async def test_i_latency(cpu_budget: asyncio.Semaphore) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-re", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2",
        "-c:v", "libx264", "-preset", "ultrafast",
        "dummy_latency.mp4"
    ]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=2.0)
    
    latencies = []
    
    async def pinger() -> None:
        for _ in range(15):
            t1 = time.perf_counter()
            await asyncio.sleep(0.1)
            t2 = time.perf_counter()
            latencies.append((t2 - t1) - 0.1)
            
    ping_task = asyncio.create_task(pinger())
    
    async for _ in runner.run(cmd, "dummy_latency.mp4"):
        pass
        
    await ping_task
    
    max_latency = max(latencies)
    print(f"Max gecikme: {max_latency*1000:.1f}ms")
    assert max_latency < 0.100, f"Event loop bloke oldu! Max gecikme: {max_latency*1000:.1f}ms"
    if os.path.exists("dummy_latency.mp4"):
        os.remove("dummy_latency.mp4")

@pytest.mark.asyncio
async def test_j_early_close_stall(cpu_budget: asyncio.Semaphore) -> None:
    # (i) stdout erken kapanır, süreç yaşar → stall ile ≤ eşik+ε içinde öldürülür
    script_path = "mock_early_close.py"
    with open(script_path, "w") as f:
        f.write("import sys, time\nsys.stdout.close()\ntime.sleep(10)\n")
                
    cmd = [sys.executable, script_path, "dummy_early.mp4"]
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=10.0, stall_timeout_sec=0.5, initial_stall_timeout_sec=0.5)
    
    start = time.time()
    with pytest.raises(RenderStalled):
        async for _ in runner.run(cmd, "dummy_early.mp4"):
            pass
            
    dur = time.time() - start
    assert dur < 2.0, "Stall eşiği + epsilon'da iptal edilmedi"
    os.remove(script_path)

@pytest.mark.asyncio
async def test_k_drainage_child_pipe(cpu_budget: asyncio.Semaphore) -> None:
    # (ii) süreç çıkar, pipe'ı bir artakalan süreç tutar → boşaltma süresi (2 sn) sonunda döner
    script_path = "mock_drainage.py"
    with open(script_path, "w") as f:
        f.write("import sys, subprocess\nsubprocess.Popen([sys.executable, '-c', 'import time, sys; sys.stdout.write(\"x\"); sys.stdout.flush(); time.sleep(10)'], stdout=sys.stdout, stderr=sys.stderr)\nsys.exit(0)\n")
                
    cmd = [sys.executable, script_path, "dummy_drainage.mp4"]
    # Normalde timeout 10s. Süreç hemen (0.1sn) çıkacak ama child pipe'ı 10sn tutacak.
    # Runner boşaltma (drainage) mekanizması ile en fazla 2sn bekleyip iptal edecek.
    runner = FFmpegRunner(cpu_budget=cpu_budget, target_duration_sec=5.0, timeout_sec=10.0)
    
    start = time.time()
    try:
        async for _ in runner.run(cmd, "dummy_drainage.mp4"):
            pass
    except RenderFailed: # çıktı dosyası (.part -> .mp4) olmadığı için failed yiyecektir
        pass
        
    dur = time.time() - start
    # Süreç 0s'de çıktı, drainage tam 2s. Toplam 2 saniye civarı olmalı (10 saniye beklememeli!)
    assert 1.5 < dur < 3.0, f"Drenaj mekanizması çalışmadı, geçen süre: {dur:.1f}s"
    os.remove(script_path)
