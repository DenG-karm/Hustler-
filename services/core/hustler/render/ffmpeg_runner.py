import sys
import os
import asyncio
import collections
import contextlib
import subprocess
from typing import List, AsyncGenerator, Any, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

class HustlerError(Exception):
    """Genel sistem hatası"""
    pass

class RenderTimeout(HustlerError):
    """Toplam süre aşıldı"""
    pass

class RenderStalled(HustlerError):
    """FFmpeg ilerlemesi durdu"""
    pass

class RenderFailed(HustlerError):
    """FFmpeg hata ile çıktı"""
    def __init__(self, message: str, raw_stderr: str):
        super().__init__(message)
        self.raw_stderr = raw_stderr

class NvencUnavailableError(RenderFailed):
    """NVENC donanım hızlandırması kullanılamıyor"""
    pass

@dataclass
class RenderProgress:
    progress: float

@dataclass
class RenderComplete:
    output_path: str

# K-607b Kural 8: Proactor doğrulama
if sys.platform == "win32":
    try:
        _loop = asyncio.get_running_loop()
        if not isinstance(_loop, asyncio.ProactorEventLoop):
            raise RuntimeError("Windows üzerinde subprocess desteği için ProactorEventLoop zorunludur!")
    except RuntimeError as e:
        if "ProactorEventLoop" in str(e):
            raise
        else:
            _policy = asyncio.get_event_loop_policy()
            if not isinstance(_policy, asyncio.WindowsProactorEventLoopPolicy):
                raise RuntimeError("Windows üzerinde subprocess desteği için ProactorEventLoop zorunludur!")

class FFmpegRunner:
    def __init__(self, cpu_budget: asyncio.Semaphore, total_frames: Optional[int] = None, target_duration_sec: Optional[float] = None, timeout_sec: float = 300.0, stall_timeout_sec: float = 30.0, initial_stall_timeout_sec: float = 30.0) -> None:
        self.cpu_budget = cpu_budget
        self.total_frames = total_frames
        self.target_time_us = (target_duration_sec * 1_000_000) if target_duration_sec else None
        self.timeout_sec = timeout_sec
        self.stall_timeout_sec = stall_timeout_sec
        self.initial_stall_timeout_sec = initial_stall_timeout_sec

    def _parse_progress(self, line: str, current_progress: float) -> Optional[float]:
        if "N/A" in line:
            return None
        
        if line.startswith("frame="):
            if self.total_frames:
                try:
                    f = float(line.split("=")[1].strip())
                    if f > 0:
                        return (f / self.total_frames) * 100.0
                except ValueError:
                    pass
        elif line.startswith("out_time_us="):
            if self.target_time_us:
                try:
                    us_str = line.split("=")[1].strip()
                    if us_str.isdigit() or (us_str.startswith("-") and us_str[1:].isdigit()):
                        us = float(us_str)
                        if us > 0:
                            return (us / self.target_time_us) * 100.0
                except ValueError:
                    pass
        return None

    def _classify_error(self, stderr: str) -> RenderFailed:
        lower_err = stderr.lower()
        if "no such filter" in lower_err or "error initializing complex filters" in lower_err or "error parsing" in lower_err:
            return RenderFailed("FFmpeg filtre grafı geçersiz.", stderr)
        if "no such file or directory" in lower_err:
            return RenderFailed("Girdi dosyalarından biri bulunamadı.", stderr)
        if "no space left on device" in lower_err:
            return RenderFailed("Diskte yer kalmadı.", stderr)
        if "nvenc" in lower_err and ("not found" in lower_err or "failed" in lower_err or "no nvenc capable devices found" in lower_err):
            return NvencUnavailableError("NVENC donanım hızlandırıcısı başlatılamadı.", stderr)
            
        return RenderFailed("Bilinmeyen FFmpeg hatası.", stderr)

    async def run(self, cmd: List[str], output_path: str) -> AsyncGenerator[Any, None]:
        part_path = output_path + ".part"
        if cmd[-1] != part_path:
            cmd.pop()
            ext = output_path.rsplit('.', 1)[-1].lower()
            cmd.extend(["-f", ext, part_path])

        is_ffmpeg = "ffmpeg" in os.path.basename(cmd[0]).lower()
        if is_ffmpeg:
            if "-progress" not in cmd:
                cmd = [cmd[0], "-nostats", "-progress", "pipe:1"] + cmd[1:]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            if is_ffmpeg and "-nostdin" not in cmd:
                cmd = [cmd[0], "-nostdin"] + cmd[1:]

        async with self.cpu_budget:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=creationflags
            )
            
            assert proc.stdout is not None
            assert proc.stderr is not None
            
            stderr_buffer: collections.deque[str] = collections.deque(maxlen=1000)
            
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            last_progress_time = start_time
            last_yield_time = 0.0
            current_progress = 0.0
            
            progress_queue: asyncio.Queue[float] = asyncio.Queue()
            
            async def read_stdout() -> None:
                try:
                    while True:
                        line_bytes = await proc.stdout.readline() # type: ignore[union-attr]
                        if not line_bytes:
                            break
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        p = self._parse_progress(line, current_progress)
                        if p is not None:
                            await progress_queue.put(p)
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                finally:
                    await progress_queue.put(float('-inf'))
                    
            async def read_stderr() -> None:
                try:
                    while True:
                        line_bytes = await proc.stderr.readline() # type: ignore[union-attr]
                        if not line_bytes:
                            break
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        stderr_buffer.append(line)
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

            try:
                async with asyncio.TaskGroup() as tg:
                    stdout_task = tg.create_task(read_stdout())
                    stderr_task = tg.create_task(read_stderr())
                    
                    while True:
                        elapsed = loop.time() - start_time
                        rem = self.timeout_sec - elapsed
                        if rem <= 0:
                            raise RenderTimeout("Toplam render süresi aşıldı.")
                            
                        current_stall = self.initial_stall_timeout_sec if current_progress == 0.0 else self.stall_timeout_sec
                        stall_elapsed = loop.time() - last_progress_time
                        if stall_elapsed > current_stall:
                            raise RenderStalled("FFmpeg ilerlemesi durdu (Stall).")
                            
                        try:
                            p = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                            if p != float('-inf'):
                                last_progress_time = loop.time()
                                if p > current_progress:
                                    current_progress = p
                                    
                                clamped_p = min(max(current_progress, 0.0), 99.9)
                                
                                now = loop.time()
                                if now - last_yield_time >= 0.25:
                                    yield RenderProgress(progress=clamped_p)
                                    last_yield_time = now
                        except asyncio.TimeoutError:
                            pass
                            
                        if proc.returncode is not None:
                            drain_start = loop.time()
                            while not (stdout_task.done() and stderr_task.done()):
                                if loop.time() - drain_start > 2.0:
                                    stdout_task.cancel()
                                    stderr_task.cancel()
                                    break
                                try:
                                    p = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                                    if p != float('-inf'):
                                        if p > current_progress:
                                            current_progress = p
                                        clamped_p = min(max(current_progress, 0.0), 99.9)
                                        now = loop.time()
                                        if now - last_yield_time >= 0.25:
                                            yield RenderProgress(progress=clamped_p)
                                            last_yield_time = now
                                except asyncio.TimeoutError:
                                    pass
                            break

                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
                    
                if proc.returncode is not None and proc.returncode != 0:
                    raw_stderr = "\n".join(stderr_buffer)
                    logger.error("FFmpeg Error Trace", trace=raw_stderr[:500] + "...")
                    raise self._classify_error(raw_stderr)
                    
                if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
                    os.replace(part_path, output_path)
                    yield RenderProgress(progress=100.0)
                    yield RenderComplete(output_path=output_path)
                else:
                    raise RenderFailed("Çıktı dosyası oluşturulamadı veya boş.", "\n".join(stderr_buffer))

            except (Exception, asyncio.CancelledError) as e:
                await self._kill_process(proc)
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except OSError:
                        logger.warning("Artık .part dosyası silinemedi.", dosya=part_path)
                        
                if hasattr(e, "exceptions"):
                    for exc in getattr(e, "exceptions"):
                        if isinstance(exc, HustlerError):
                            raise exc
                    raise getattr(e, "exceptions")[0]
                raise e
            finally:
                # Okuyucular iptal edilirse Windows Proactor pipe/transport sızar (ResourceWarning).
                transport = getattr(proc, "_transport", None)
                if transport is not None:
                    transport.close()

    async def _kill_process(self, proc: asyncio.subprocess.Process | None) -> None:
        """
        Windows'ta terminate==kill; çıktı zaten atılacağı için graceful 'q' gerekmez.
        """
        if proc is None:
            return
        if proc.returncode is not None:
            return
            
        try:
            async def _kill_and_wait() -> None:
                proc.kill()
                await proc.wait()
                
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(_kill_and_wait()), timeout=2.0)
        except (ProcessLookupError, OSError):
            pass
