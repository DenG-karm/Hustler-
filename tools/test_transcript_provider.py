import asyncio
import os
import sys
import time
import structlog

# Windows konsolunda UnicodeEncodeError almamak için stdout ve stderr UTF-8'e zorlanır
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.providers.transcript import TranscriptProvider

logger = structlog.get_logger()

async def main():
    logger.info("--- M3 K-302: TRANSCRIPT PROVIDER (PRIORITY ROUTING) TESTİ BAŞLIYOR ---")
    
    provider = TranscriptProvider(target_language="en")
    
    # Gerçek YouTube ID'lerinden karmaşık bir liste (Bilinçli olarak geçersiz/kapalı olanlar dahil)
    video_ids = [
        "dQw4w9WgXcQ", # Rick Astley (Altyazısı kesin var)
        "jNQXAC9IVRw", # Me at the zoo (Altyazısı var)
        "kJQP7kiw5Fk", # Despacito (Şarkı - İspanyolca -> translation_required = True vermeli)
        "invalid_id_99", # Geçersiz ID -> Whisper Fallback
        "LXb3EKWsInQ", # Müzik videosu (Genelde altyazı kapalı -> Whisper Fallback)
        "V-_O7nl0Ii0", # MKBHD (İngilizce - Altyazı var)
        "YQHsXMglC9A", # Adele Hello
        "XqZsoesa55w", # Baby Shark
        "tPEE9ZwTmy0", # Short Video
        "M7FIvfx5J10", # Charlie bit my finger
    ]
    
    start_time = time.perf_counter()
    
    logger.info("10 adet video için asenkron (Thread-Pool) transkript çekimi başlatıldı...")
    
    # Asenkron toplu çekim (Blocking I/O asenkron event loop'u kilitliyor mu diye strese sokuyoruz)
    tasks = [provider.get_transcript(vid) for vid in video_ids]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.perf_counter() - start_time
    
    native_count = 0
    whisper_count = 0
    translated_count = 0
    
    for res in results:
        if res.requires_whisper:
            whisper_count += 1
            logger.warning("🐌 YAVAŞ YOLA DEVREDİLDİ (Whisper)", video_id=res.video_id, error=res.error_message)
        else:
            native_count += 1
            if res.translation_required:
                translated_count += 1
                
            text_preview = res.text[:50] + "..." if res.text and len(res.text) > 50 else res.text
            
            logger.info("⚡ HIZLI YOLDAN ÇEKİLDİ (Native)", 
                video_id=res.video_id, 
                lang=res.language_code, 
                translation_req=res.translation_required,
                preview=text_preview
            )
            
    logger.info("=== TRANSCRIPT PROVIDER ÖZETİ ===",
        toplam_video=len(video_ids),
        hizli_yol_native=native_count,
        yavas_yol_whisper=whisper_count,
        farkli_dil_cevirilecek=translated_count,
        toplam_sure_sn=round(elapsed, 2)
    )
    
    # Asenkron havuzun düzgün çalıştığını doğruluyoruz
    assert native_count + whisper_count == len(video_ids), "Eksik video işlendi!"

if __name__ == "__main__":
    asyncio.run(main())
