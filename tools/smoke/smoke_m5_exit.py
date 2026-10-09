import sys
import os
import time
import asyncio
import structlog
import aiofiles

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.tts_port import ElevenLabsAdapter
from services.core.hustler.infrastructure.audio_cache import AudioCache
from services.core.hustler.infrastructure.timestamp_normalizer import TimestampNormalizer
from services.core.hustler.generators.subtitle_generator import AssDocument, SubtitleStyle
from services.core.hustler.infrastructure.timecode import TimeCode, SceneSynchronizer

logger = structlog.get_logger()

# Ağ (I/O) kısmını mocklayan ancak tam adaptör davranışını sergileyen sınıf
class MockM5ExitTTSAdapter(ElevenLabsAdapter):
    def __init__(self) -> None:
        super().__init__(api_key="MOCK_API")
        self.api_call_count = 0
        
    async def generate_audio_stream(self, text: str, output_path: str, voice_id: str) -> None:
        self.api_call_count += 1
        logger.warning(f"🌐 MOCK TTS ÇAĞRISI (Ağ üzerinden dosya indiriliyor...) | Çağrı No: {self.api_call_count}")
        # Diske Mock Chunk Streaming
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(b"mock_audio_stream_data_for_exit_test_chunk_1")
        await asyncio.sleep(0.01) # Ağ Gecikmesi simülasyonu

async def main() -> None:
    logger.info("--- M5 ÇIKIŞ KRİTERLERİ (EXIT CRITERIA) DOĞRULAMA TESTİ ---")
    
    # 1. Bağımlılıkları Kur
    test_cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', '.cache', 'm5_exit_audio')
    audio_cache = AudioCache(cache_dir=test_cache_dir)
    tts_adapter = MockM5ExitTTSAdapter()
    
    script_text = "M5 fazının tüm entegrasyonları burada kusursuzca test edilecek."
    voice_id = "test_voice_m5"
    scene_count = 3
    
    # API'den geldiği varsayılan ham (Raw) kelime hizalamaları (Float saniye)
    raw_alignments = [
        {"word": "M5", "start": 0.000, "end": 0.400},
        {"word": "fazının", "start": 0.400, "end": 0.900},
        {"word": "tüm", "start": 0.900, "end": 1.200},
        {"word": "entegrasyonları", "start": 1.250, "end": 2.500},
        {"word": "burada", "start": 2.500, "end": 3.100},
        {"word": "kusursuzca", "start": 3.100, "end": 3.900},
        {"word": "test", "start": 3.900, "end": 4.300},
        {"word": "edilecek.", "start": 4.300, "end": 5.1234} # Küsuratlı bitiş (5123.4 ms)
    ]
    
    # Test ortamı temizliği
    cache_key = audio_cache._generate_cache_key(script_text, voice_id)
    expected_audio_file = os.path.join(test_cache_dir, f"{cache_key}.mp3")
    if os.path.exists(expected_audio_file):
        os.remove(expected_audio_file)
        
    logger.info(">>> 1. UÇTAN UCA ENTEGRASYON VE GECİKME ÖLÇÜMÜ (I/O HARİÇ) <<<")
    
    # Bellek İçi Hesaplama Gecikmesini (Latency) Ölçmeye Başla
    start_time = time.perf_counter()
    
    # K-502: Zaman Damgası Normalizasyonu
    normalized_words = TimestampNormalizer.normalize_timings(raw_alignments)
    
    # K-503: .ass Altyazı Derlemesi
    style = SubtitleStyle(font_name='Arial', font_size=20, primary_color='&H00FFFFFF', highlight_color='&H000000FF', alignment=5, margin_v=10)
    ass_content = AssDocument.generate(normalized_words, style)
    
    # K-505: Sahne Senkronizasyonu
    # Toplam ses süresini son kelimenin bitiş anından alıyoruz
    total_audio_ms_from_words = normalized_words[-1].end_ms
    scenes = SceneSynchronizer.sync_scenes(total_audio_ms_from_words, scene_count)
    
    end_time = time.perf_counter()
    latency_ms = (end_time - start_time) * 1000
    
    logger.info("Bellek İçi Hesaplama Süresi (Latency)", sure_ms=f"{latency_ms:.3f} ms")
    assert latency_ms < 50.0, f"KRİTİK HATA: Gecikme 50ms sınırını aştı! ({latency_ms} ms)"
    logger.info("✅ Gecikme Testi Başarılı: Normalizasyon, Altyazı Derleme ve Frame hesaplamaları <50ms içinde tamamlandı.")
    
    # --- 2. SENKRON BÜTÜNLÜĞÜ (DRIFT PREVENTION) KONTROLÜ ---
    logger.info(">>> 2. SENKRON BÜTÜNLÜĞÜ (DRIFT) KONTROLÜ <<<")
    
    # Sahnelerin frame cinsinden toplamı
    total_scene_frames = sum(s["frames"] for s in scenes)
    calculated_scenes_ms = TimeCode.frames_to_ms(total_scene_frames)
    
    last_word_end_ms = normalized_words[-1].end_ms
    sync_diff = abs(last_word_end_ms - calculated_scenes_ms)
    tolerance = int(1000 / TimeCode.FPS) + 1 # ~34ms
    
    logger.info(
        "Senkron Eşleşmesi", 
        altyazi_bitis_ms=last_word_end_ms, 
        sahne_toplam_ms=calculated_scenes_ms, 
        sapma_ms=sync_diff
    )
    
    assert sync_diff <= tolerance, f"KRİTİK HATA: Senkron kayması! Altyazı Bitişi: {last_word_end_ms}, Sahneler Bitişi: {calculated_scenes_ms}"
    logger.info("✅ Senkron Bütünlüğü Başarılı: Altyazı bitiş süresi ile sahnelerin toplam süresi (FPS tabanlı) tam eşleşti.")
    
    # --- 3. CACHE VE AĞ (I/O) KONTROLÜ ---
    logger.info(">>> 3. ÖNBELLEK (CACHE) İSPATI <<<")
    
    # 1. Tetikleme (API'ye gitmeli)
    path_1 = await audio_cache.get_or_fetch(
        script_text, 
        voice_id, 
        lambda p: tts_adapter.generate_audio_stream(script_text, p, voice_id)
    )
    
    # 2. Tetikleme (Diskten dönmeli)
    path_2 = await audio_cache.get_or_fetch(
        script_text, 
        voice_id, 
        lambda p: tts_adapter.generate_audio_stream(script_text, p, voice_id)
    )
    
    assert path_1 == path_2, "HATA: Önbellek farklı yollar döndürdü!"
    assert tts_adapter.api_call_count == 1, f"KRİTİK HATA: Önbellek bozuk, API'ye {tts_adapter.api_call_count} kez gidildi!"
    
    logger.info("✅ Önbellek İspatı Başarılı: İlk çağrı sonrası API iletişimi tamamen kesildi (Cache Hit).")
    
    logger.info("=====================================================")
    logger.info("🚀 M5 FAZI (SES VE ALTYAZI) BAŞARIYLA TAMAMLANDI! 🚀")
    logger.info("Sistem; tam senkronize altyazılar, sıfır çerçeve kayması ve akıllı önbellek ile M6 (Render) fazına hazır.")
    logger.info("=====================================================")

if __name__ == "__main__":
    asyncio.run(main())
