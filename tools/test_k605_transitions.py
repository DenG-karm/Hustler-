import sys
import os
import structlog

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.generators.transition_planner import TransitionPlanner
from services.core.hustler.generators.audio_mixer import AudioMixer
from tools.test_ffmpeg_compiler import assert_compiles

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M6 K-605: TRANSITION PLANNER VE AUDIO MIXER TESTİ ---")
    
    # 1. Birim Test (Unit Test): Ofset Matematiği
    durations = [5.0, 4.0, 3.0]
    transition_sec = 0.5
    
    offsets = TransitionPlanner.calculate_offsets(durations, transition_sec)
    
    # Beklenen: [4.5, 8.0]
    assert len(offsets) == 2, f"Beklenen 2 ofset, alınan {len(offsets)}"
    assert abs(offsets[0] - 4.5) < 0.001, f"1. ofset hatası. Beklenen: 4.5, Alınan: {offsets[0]}"
    assert abs(offsets[1] - 8.0) < 0.001, f"2. ofset hatası. Beklenen: 8.0, Alınan: {offsets[1]}"
    
    logger.info("✅ Xfade Ofset Matematiği Doğrulandı!", ofsetler=offsets)
    
    # 2. Dry-Run Testi: Graf İnşası
    video_labels = ["0:v", "1:v", "2:v"]
    xfade_lines, final_v = TransitionPlanner.build_graph(video_labels, durations, transition_sec)
    
    logger.info("Xfade AST Grafı Üretildi", graf=xfade_lines)
    
    audio_lines, final_a = AudioMixer.build_mix_graph("3:a", "4:a")
    
    logger.info("Audio Mix AST Grafı Üretildi", graf=audio_lines)
    
    filter_complex = ";".join(xfade_lines + audio_lines)
    
    # Sanal Komutu Hazırla (lavfi kaynakları kullanarak)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=1080x1920:d=5",
        "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=4",
        "-f", "lavfi", "-i", "color=c=green:s=1080x1920:d=3",
        "-f", "lavfi", "-i", "aevalsrc=0:d=10",
        "-f", "lavfi", "-i", "aevalsrc=0:d=10",
        "-filter_complex", filter_complex,
        "-map", f"[{final_v}]",
        "-map", f"[{final_a}]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "output.mp4"
    ]
    
    logger.info("Dry Run Öncesi Hazırlanan Komut", komut=" ".join(cmd))
    
    # K-603 dry-run yardımcısı (assert_compiles) ile disk I/O olmadan (NUL) test et
    assert_compiles(cmd, "test_assets/dummy_sub.ass")
    
    logger.info("--- K-605 TESTİ BAŞARIYLA TAMAMLANDI ---")

if __name__ == '__main__':
    main()
