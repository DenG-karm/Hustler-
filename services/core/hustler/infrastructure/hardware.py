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

async def measure_and_save_profile(db: Database) -> dict:
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
