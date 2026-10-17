import asyncio
import collections
import contextlib
import os
import subprocess
import sys
from typing import AsyncGenerator, List, Optional, Any
from dataclasses import dataclass
import structlog

from services.core.hustler.render.job_object import bind_pid_to_kill_on_close_job

logger = structlog.get_logger()

# -----------------------------------------------------------------------------
# Olay ve Hata Sınıfları (Events & Exceptions)
# -----------------------------------------------------------------------------
@dataclass
class RenderProgress:
    progress: float

@dataclass
class RenderComplete:
    output_path: str

class HustlerError(Exception):
    """Tüm Hustler özel istisnalarının taban sınıfı."""
    pass

class RenderFailed(HustlerError):
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(f"{message} | Detay: {stderr[-500:]}" if stderr else message)
        self.stderr = stderr

class RenderTimeout(RenderFailed):
    pass

class RenderStalled(RenderFailed):
    pass

class NvencUnavailableError(RenderFailed):
    pass

# -----------------------------------------------------------------------------
# FFmpegRunner Sınıfı
# -----------------------------------------------------------------------------
class FFmpegRunner:
    """
    M6 K-604: Güvenli ve Asenkron FFmpeg Yürütücüsü (Runner)
    """
    def __init__(
        self,
        cpu_budget: asyncio.Semaphore,
        total_frames: Optional[int] = None,
        target_duration_sec: Optional[float] = None,
        timeout_sec: float = 300.0,
        stall_timeout_sec: float = 15.0,
        initial_stall_timeout_sec: float = 30.0,
    ):
        self.cpu_budget = cpu_budget
        self.total_frames = total_frames
        self.target_time_us = (target_duration_sec * 1_000_000) if target_duration_sec else None
        self.timeout_sec = timeout_sec
        self.stall_timeout_sec = stall_timeout_sec
        self.initial_stall_timeout_sec = initial_stall_timeout_sec

    def _parse_frame_progress(self, line: str) -> Optional[float]:
        """frame= satırından yüzde hesaplar."""
        if not self.total_frames or not line.startswith("frame="):
            return None
        try:
            f = float(line.split("=")[1].strip())
            return (f / self.total_frames) * 100.0 if f > 0 else None
        except ValueError:
            return None

    def _parse_time_progress(self, line: str) -> Optional[float]:
        """out_time_us= satırından yüzde hesaplar."""
        if not self.target_time_us or not line.startswith("out_time_us="):
            return None
        try:
            us_str = line.split("=")[1].strip()
            if us_str.isdigit() or (us_str.startswith("-") and us_str[1:].isdigit()):
                us = float(us_str)
                return (us / self.target_time_us) * 100.0 if us > 0 else None
            return None
        except ValueError:
            return None

    def _parse_progress(self, line: str, current_progress: float) -> Optional[float]:
        if "N/A" in line:
            return None
        return self._parse_frame_progress(line) or self._parse_time_progress(line)

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

    def _prepare_command(self, cmd: List[str], output_path: str) -> tuple[List[str], str, int]:
        """Komut dizisini part_path ve platform bayraklarıyla hazırlar."""
        cmd_copy = list(cmd)
        part_path = output_path + ".part"
        if cmd_copy[-1] != part_path:
            cmd_copy.pop()
            ext = output_path.rsplit('.', 1)[-1].lower()
            muxer_map = {"mp4": "mp4", "mkv": "matroska", "wav": "wav", "webm": "webm", "ass": "ass"}
            muxer = muxer_map.get(ext, ext)
            cmd_copy.extend(["-f", muxer, part_path])

        is_ffmpeg = "ffmpeg" in os.path.basename(cmd_copy[0]).lower()
        if is_ffmpeg and "-progress" not in cmd_copy:
            cmd_copy = [cmd_copy[0], "-nostats", "-progress", "pipe:1"] + cmd_copy[1:]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            if is_ffmpeg and "-nostdin" not in cmd_copy:
                cmd_copy = [cmd_copy[0], "-nostdin"] + cmd_copy[1:]

        return cmd_copy, part_path, creationflags

    async def _spawn_process(self, cmd: List[str], creationflags: int) -> asyncio.subprocess.Process:
        """FFmpeg alt sürecini başlatır ve Windows JobObject'e bağlar."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        if sys.platform == "win32":
            bind_pid_to_kill_on_close_job(proc.pid)
        return proc

    async def _drain_remaining_progress(
        self,
        loop: asyncio.AbstractEventLoop,
        tasks: list[asyncio.Task[None]],
        progress_queue: asyncio.Queue[float],
        current_progress: float,
        last_yield_time: float,
    ) -> AsyncGenerator[RenderProgress, None]:
        """Süreç bittikten sonra kalan kuyruk öğelerini tahliye eder."""
        drain_start = loop.time()
        while not (tasks[0].done() and tasks[1].done()):
            if loop.time() - drain_start > 2.0:
                tasks[0].cancel()
                tasks[1].cancel()
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

    async def _read_stdout_pipe(
        self,
        proc: asyncio.subprocess.Process,
        progress_queue: asyncio.Queue[float],
        current_progress: float,
    ) -> None:
        """Stdout borusundan satırları okur ve ayrıştırılan ilerlemeyi kuyruğa atar."""
        try:
            while True:
                line_bytes = await proc.stdout.readline()  # type: ignore[union-attr]
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                p = self._parse_progress(line, current_progress)
                if p is not None:
                    await progress_queue.put(p)
        except (asyncio.CancelledError, Exception):
            pass
        finally:
            await progress_queue.put(float('-inf'))

    @staticmethod
    async def _read_stderr_pipe(
        proc: asyncio.subprocess.Process,
        stderr_buffer: collections.deque[str],
    ) -> None:
        """Stderr borusundan satırları okur ve tampona yazar."""
        try:
            while True:
                line_bytes = await proc.stderr.readline()  # type: ignore[union-attr]
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                stderr_buffer.append(line)
        except (asyncio.CancelledError, Exception):
            pass

    def _check_timeouts(
        self,
        elapsed: float,
        last_progress_time: float,
        current_progress: float,
        now: float,
    ) -> None:
        """Genel zaman aşımı ve donma (stall) denetimi yapar."""
        if self.timeout_sec - elapsed <= 0:
            raise RenderTimeout("Toplam render süresi aşıldı.")
        current_stall = self.initial_stall_timeout_sec if current_progress == 0.0 else self.stall_timeout_sec
        if now - last_progress_time > current_stall:
            raise RenderStalled("FFmpeg ilerlemesi durdu (Stall).")

    @staticmethod
    async def _pop_progress(progress_queue: asyncio.Queue[float]) -> float | None:
        """Kuyruktan ilerleme verisi çeker, zaman aşımında None döner."""
        try:
            return await asyncio.wait_for(progress_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def _stream_and_track_progress(
        self,
        proc: asyncio.subprocess.Process,
        stderr_buffer: collections.deque[str],
    ) -> AsyncGenerator[RenderProgress, None]:
        """Stdout ve stderr borularını izler, ilerleme ve stall/timeout denetimi yapar."""
        assert proc.stdout is not None
        assert proc.stderr is not None

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        last_progress_time = start_time
        last_yield_time = 0.0
        current_progress = 0.0

        progress_queue: asyncio.Queue[float] = asyncio.Queue()

        async with asyncio.TaskGroup() as tg:
            stdout_task = tg.create_task(self._read_stdout_pipe(proc, progress_queue, current_progress))
            stderr_task = tg.create_task(self._read_stderr_pipe(proc, stderr_buffer))

            while True:
                now = loop.time()
                self._check_timeouts(now - start_time, last_progress_time, current_progress, now)

                p = await self._pop_progress(progress_queue)
                if p == float('-inf'):
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(proc.wait(), timeout=1.0)
                    async for prog in self._drain_remaining_progress(
                        loop, [stdout_task, stderr_task], progress_queue, current_progress, last_yield_time
                    ):
                        yield prog
                    break

                if p is not None:
                    last_progress_time = loop.time()
                    current_progress = max(current_progress, p)
                    clamped_p = min(max(current_progress, 0.0), 99.9)
                    if now - last_yield_time >= 0.25:
                        yield RenderProgress(progress=clamped_p)
                        last_yield_time = now

                if proc.returncode is not None:
                    async for prog in self._drain_remaining_progress(
                        loop, [stdout_task, stderr_task], progress_queue, current_progress, last_yield_time
                    ):
                        yield prog
                    break

    async def _finalize_atomic_output(
        self,
        proc: asyncio.subprocess.Process,
        part_path: str,
        output_path: str,
        stderr_buffer: collections.deque[str],
    ) -> AsyncGenerator[Any, None]:
        """Süreç dönüş kodunu ve atomik dosya yer değiştirmesini yönetir."""
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

    async def _cleanup_on_cancel(
        self,
        proc: asyncio.subprocess.Process,
        part_path: str,
        e: BaseException,
    ) -> None:
        """Hata veya iptal anında süreci öldürür ve .part dosyasını temizler."""
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

    async def run(self, cmd: List[str], output_path: str) -> AsyncGenerator[Any, None]:
        cmd_prepared, part_path, creationflags = self._prepare_command(cmd, output_path)

        async with self.cpu_budget:
            proc = await self._spawn_process(cmd_prepared, creationflags)
            stderr_buffer: collections.deque[str] = collections.deque(maxlen=1000)

            try:
                async for progress in self._stream_and_track_progress(proc, stderr_buffer):
                    yield progress
                async for event in self._finalize_atomic_output(proc, part_path, output_path, stderr_buffer):
                    yield event
            except (Exception, asyncio.CancelledError) as e:
                await self._cleanup_on_cancel(proc, part_path, e)
            finally:
                transport = getattr(proc, "_transport", None)
                if transport is not None:
                    transport.close()

    async def _kill_process(self, proc: asyncio.subprocess.Process | None) -> None:
        if proc is None or proc.returncode is not None:
            return
        try:
            async def _kill_and_wait() -> None:
                proc.kill()
                await proc.wait()

            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(_kill_and_wait()), timeout=2.0)
        except (ProcessLookupError, OSError):
            pass
