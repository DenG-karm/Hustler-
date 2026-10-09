import asyncio
import os
import re
import subprocess
import time
import httpx
import structlog
import sys

logger = structlog.get_logger()

async def main() -> None:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.error("YOUTUBE_API_KEY eksik!")
        return

    logger.info("FastAPI Sunucusu (Sidecar) ayağa kaldırılıyor...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Ana uygulamayı bir Subprocess olarak başlat
    proc = subprocess.Popen(
        [sys.executable, "-m", "services.core.hustler.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    
    port = None
    token = None
    
    # Uygulamanın stdout çıktısını okuyarak Port ve Token'ı çek
    start_time = time.time()
    while time.time() - start_time < 15:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            continue
            
        print(line.strip()) # Debug amaçlı
            
        if "HUSTLER_BIND" in line:
            match = re.search(r"PORT=(\d+)::TOKEN=([\w-]+)", line)
            if match:
                port = int(match.group(1))
                token = match.group(2)
                break
                
    if not port or not token:
        logger.error("Port ve Token alınamadı, sunucu başlatılamadı!")
        proc.kill()
        return
        
    logger.info("Sunucuya başarıyla bağlanıldı", port=port, token=token)
    
    # REST API'ye HTTP POST İsteği
    url = f"http://127.0.0.1:{port}/api/v1/discovery/run"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "topic": "day trading smc",
        "max_results": 20,
        "score_threshold": 10.0
    }
    
    logger.info("HTTP POST isteği gönderiliyor...", url=url)
    async with httpx.AsyncClient() as client:
        # Arama işlemi uzun sürebilir, timeout'u yüksek tutuyoruz
        response = await client.post(url, json=payload, headers=headers, timeout=60.0)
        
    logger.info("--- HTTP YANITI ALINDI ---", status_code=response.status_code)
    
    if response.status_code == 200:
        data = response.json()
        logger.info("=== DISCOVERY API SONUCU (200 OK) ===", 
            toplam_cekilen=data.get("fetched"),
            cop_edilen=data.get("discarded"),
            veritabanina_yazilan=data.get("inserted")
        )
    else:
        logger.error("API Hatası", detail=response.text)
        
    # Test sonu, sunucuyu güvenli şekilde kapat
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        
    logger.info("Uçtan uca test tamamlandı, sunucu kapatıldı.")
    
if __name__ == "__main__":
    asyncio.run(main())
