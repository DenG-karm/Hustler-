import sys
import os
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.infrastructure.timecode import TimeCode, SceneSynchronizer

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M5 K-505: TIMECODE VE SCENE SYNCHRONIZER TESTİ ---")
    
    # Katı Test Parametreleri
    total_audio_ms = 11333 # Asimetrik/küsuratlı değer
    scene_count = 3
    
    logger.info(f">>> GİRDİ: Toplam Ses Süresi: {total_audio_ms} ms | Sahne Sayısı: {scene_count} <<<")
    
    # 1. MS -> Frame Dönüşümü
    total_frames = TimeCode.ms_to_frames(total_audio_ms)
    logger.info(f"Zaman Çizelgesi Hesabı ({TimeCode.FPS} FPS)", toplam_üretilen_kare=total_frames)
    
    # 2. Sahne Senkronizasyonu (Bölme ve Artık Dağıtımı)
    scenes = SceneSynchronizer.sync_scenes(total_audio_ms, scene_count)
    
    total_scene_frames = 0
    
    logger.info(">>> ÇIKTI: Sahne Dağılımları (Drift Prevention) <<<")
    for s in scenes:
        logger.info(
            f"Sahne {s['scene_index']}", 
            atanan_kare_frame=s['frames'], 
            sure_ms=s['duration_ms'],
            baslangic_ms=s['start_ms']
        )
        total_scene_frames += s['frames']
        
    # --- DOĞRULAMALAR ---
    
    # Kural 1: Kare (Frame) Toplamı Eksiksiz Olmalı (Frame Drop Yasak)
    assert total_scene_frames == total_frames, f"KRİTİK HATA: Frame sızıntısı var! Toplam {total_frames} olması gerekirken {total_scene_frames} bulundu."
    logger.info("✅ Artık Yönetimi Başarılı: Bölmeden kalan küsuratlı kareler (remainder) başarıyla sahnelere dağıtıldı, hiçbir kare (frame) kaybolmadı.")
    
    # Kural 2: MS <-> Frame Geri Dönüşümü Toleranslı Eşleşme (±1 Kare / ~33ms)
    calculated_total_ms = TimeCode.frames_to_ms(total_scene_frames)
    tolerance_ms = int(1000 / TimeCode.FPS) + 1 # 1 karelik tolerans (~34ms)
    ms_diff = abs(total_audio_ms - calculated_total_ms)
    
    assert ms_diff <= tolerance_ms, f"KRİTİK HATA: Ses ile Görüntü arasında {ms_diff} ms kayma tespit edildi! Tolerans aşıldı."
    
    logger.info(
        "✅ Senkron Kayması Yok (Sıfır Hata)", 
        orijinal_ses_ms=total_audio_ms, 
        karelerden_tekrar_hesaplanan_ms=calculated_total_ms, 
        sapma_ms=ms_diff
    )
    logger.info("--- K-505 TESTİ TAMAMLANDI ---")

if __name__ == "__main__":
    main()
