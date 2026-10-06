import sys
import os
import asyncio
import structlog
from pathlib import Path

# Windows konsolunda UnicodeEncodeError almamak için stdout ve stderr UTF-8'e zorlanır
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.infrastructure.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError, CircuitBreakerRejectedError
)

logger = structlog.get_logger()

async def dummy_whisper_operation(breaker: CircuitBreaker, duration: int, should_fail: bool):
    """Sentetik yük: CircuitBreaker bağlamında (context) çalışan işlev."""
    # Bütçe kontrolü (Devre açık olmasa bile çok uzun videoları baştan reddeder)
    breaker.check_budget(duration)
    
    # Asıl işlemin durum makinesi ile sarılması
    async with breaker:
        # Devre izin verirse buralar çalışır
        if should_fail:
            raise ValueError("GPU VRAM yetersiz: OOM (Out Of Memory) Hatası!")
        
        # İşlem simülasyonu
        await asyncio.sleep(0.1) 
        return "İşlem Başarılı"

async def main():
    logger.info("--- M3 K-303: DEVRE KESİCİ (CIRCUIT BREAKER) TESTİ ---")
    
    # Testi hızlı yapabilmek için soğuma süresini (cooldown) sadece 2 saniye tutuyoruz.
    config = CircuitBreakerConfig(
        max_consecutive_failures=3,
        cooldown_seconds=2.0,
        max_video_duration_seconds=600
    )
    breaker = CircuitBreaker("Whisper-GPU-Model", config)
    
    # 1. BÜTÇE KONTROLÜ TESTİ
    logger.info(">>> TEST 1: Video Uzunluk Bütçesi Testi (Max 600s)")
    try:
        await dummy_whisper_operation(breaker, duration=1200, should_fail=False)
    except CircuitBreakerRejectedError as e:
        logger.info("✅ Bütçe Reddi Başarılı (Fail-Fast)", error=str(e))
        
    # 2. CLOSED -> OPEN GEÇİŞİ (Art arda 3 hata)
    logger.info(">>> TEST 2: Art arda 3 Hata Simülasyonu (Closed -> Open)")
    for i in range(1, 4):
        try:
            await dummy_whisper_operation(breaker, duration=100, should_fail=True)
        except Exception as e:
            logger.info(f"Hata {i} yakalandı", exc=type(e).__name__)
            
    assert breaker.state.value == "OPEN", "Devre 3 hatadan sonra AÇIK duruma geçmedi!"
    
    # 3. OPEN DURUMUNDA FAIL-FAST TESTİ
    logger.info(">>> TEST 3: Devre Açıkken İsteklerin Anında Reddedilmesi (Fail-Fast)")
    try:
        # should_fail=False olmasına rağmen devre açık olduğu için içeri giremeyecek!
        await dummy_whisper_operation(breaker, duration=100, should_fail=False)
    except CircuitBreakerOpenError as e:
        logger.info("✅ Fail-Fast Başarılı, event-loop engellenmedi.", error=str(e))
        
    # 4. SOĞUMA SÜRESİ VE HALF-OPEN TESTİ (İyileşme)
    logger.info(">>> TEST 4: Soğuma Süresi (2 sn) Bekleniyor...")
    await asyncio.sleep(2.1)
    
    try:
        logger.info("Yarı-Açık (Half-Open) durumunda test isteği gönderiliyor...")
        await dummy_whisper_operation(breaker, duration=100, should_fail=False)
        logger.info("✅ Test isteği başarılı oldu, devre onarıldı.")
    except Exception as e:
        logger.error("Beklenmeyen hata", error=str(e))
        
    assert breaker.state.value == "CLOSED", "Devre başarılı test sonrası KAPALI duruma geçmedi!"
    
    logger.info("--- TÜM DEVRE KESİCİ TESTLERİ BAŞARIYLA TAMAMLANDI ---")

if __name__ == "__main__":
    asyncio.run(main())
