from typing import Any
import time
import asyncio
from services.core.hustler.db import Database

async def detect_cuda() -> bool:
    """
    Tembel (Lazy) CUDA Tespiti.
    PyTorch gibi GB'larca boyutundaki ağır kütüphaneleri yüklememek için
    işletim sistemi araçlarını (nvidia-smi) kullanarak donanım varlığını kontrol ederiz.
    Bu sayede uygulamanın ayağa kalkma süresi saniyelerden milisaniyelere iner.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=2.0)
        return proc.returncode == 0
    except (FileNotFoundError, asyncio.TimeoutError):
        return False
    except Exception:
        return False

HARDWARE_ENCODERS = ("h264_nvenc", "h264_amf")
SOFTWARE_ENCODER = "libx264"

async def _run_ffmpeg(args: list[str], timeout: float) -> tuple[int, str]:
    """ffmpeg'i çalıştırır; (çıkış kodu, stdout+stderr) döner. Süre aşımında süreci öldürür."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "timeout"
    return proc.returncode or 0, out.decode("utf-8", errors="replace")

async def select_video_encoder() -> str:
    """
    Donanım hızlandırmalı encoder'ı (NVENC, sonra AMF) seçer; yoksa libx264'e düşer.
    Derlemede listelenmesi yetmez (sürücü/GPU yoksa başlatma başarısız olur):
    her aday 1 karelik gerçek bir test kodlamasıyla doğrulanır.
    """
    try:
        code, listing = await _run_ffmpeg(["-encoders"], timeout=10.0)
    except FileNotFoundError:
        return SOFTWARE_ENCODER
    if code != 0:
        return SOFTWARE_ENCODER

    for encoder in HARDWARE_ENCODERS:
        if encoder not in listing:
            continue
        code, _ = await _run_ffmpeg(
            ["-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-frames:v", "1",
             "-c:v", encoder, "-f", "null", "-"],
            timeout=15.0,
        )
        if code == 0:
            return encoder
    return SOFTWARE_ENCODER

def run_rtf_benchmark() -> float:
    """
    Sistemin CPU/İşlem performansını ölçen basit matematiksel benchmark.
    Gerçek dünya (Real-Time Factor) kapasitesi için baz çizgisi oluşturur.
    """
    start_time = time.perf_counter()
    # Ortalama CPU yükü simülasyonu
    _ = sum(i * i for i in range(5_000_000))
    elapsed = time.perf_counter() - start_time
    
    # 0.2 saniyeyi 1.0 (Standart) RTF kabul edelim.
    reference_time = 0.2
    score = reference_time / max(elapsed, 0.001)
    return round(score, 2)

async def init_hardware_profile(db: Database) -> None:
    """Veritabanında hardware_profile tablosunu başlatır"""
    query = """
    CREATE TABLE IF NOT EXISTS hardware_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1), -- Sadece tek bir profil satırı tutar
        has_cuda BOOLEAN NOT NULL,
        rtf_score REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """
    await db.execute_write(query)

async def measure_and_save_profile(db: Database) -> dict[str, Any]:
    """Donanımı tarar ve sonucu veritabanına kaydeder."""
    has_cuda = await detect_cuda()
    
    # Bloklayıcı CPU işi, event loop'u kitlememesi için thread'e atılır.
    loop = asyncio.get_running_loop()
    rtf_score = await loop.run_in_executor(None, run_rtf_benchmark)
    
    await db.execute_write(
        """
        INSERT INTO hardware_profile (id, has_cuda, rtf_score, updated_at) 
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET 
            has_cuda=excluded.has_cuda, 
            rtf_score=excluded.rtf_score, 
            updated_at=excluded.updated_at
        """,
        (has_cuda, rtf_score, time.time())
    )
    
    return {"has_cuda": has_cuda, "rtf_score": rtf_score}
