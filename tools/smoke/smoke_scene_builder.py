import sys
import os
import structlog

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.generators.scene_builder import SceneClipBuilder
from tools.smoke.smoke_ffmpeg_compiler import assert_compiles

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M6 K-604: SCENE CLIP BUILDER VE MOTION REGISTRY TESTİ ---")
    builder = SceneClipBuilder()
    
    # 1. Video Zinciri (Animasyonsuz, sadece scale/crop)
    video_chain = builder.build_clip_chain("dummy.mp4", is_video=True, duration=3.0)
    logger.info(">>> VIDEO İÇİN ÜRETİLEN ZİNCİR <<<", ast=video_chain.to_string())
    
    # 2. Resim Zinciri (Zoompan Animasyonlu)
    image_chain = builder.build_clip_chain("dummy.jpg", is_video=False, duration=3.0)
    logger.info(">>> RESİM İÇİN ÜRETİLEN ZİNCİR (SNAPSHOT) <<<", ast=image_chain.to_string())
    
    # Dry Run Doğrulaması İçin Komut Hazırlığı
    # Sanal girdiler lavfi color üzerinden olacak. Test için basit bir ffmpeg komutu kuralım
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=1",  # Girdi 0: Video (1 saniye)
        "-f", "lavfi", "-i", "color=c=red:s=1280x720:d=1",   # Girdi 1: Resim (1 saniye)
        "-filter_complex",
        f"[0:v]{video_chain.to_string()}[v0];[1:v]{image_chain.to_string()}[v1];[v0][v1]concat=n=2:v=1:a=0[out_v]",
        "-map", "[out_v]",
        "-c:v", "libx264",
        "output.mp4"
    ]
    
    logger.info("Dry Run Öncesi Hazırlanan AST Tabanlı Komut", komut=" ".join(cmd))
    
    # K-603'teki assert_compiles metodu I/O dosyalarını null muxer'a atarak validate eder
    assert_compiles(cmd, "test_assets/dummy_sub.ass")
    
    logger.info("--- K-604 TESTİ BAŞARIYLA TAMAMLANDI ---")

if __name__ == '__main__':
    main()
