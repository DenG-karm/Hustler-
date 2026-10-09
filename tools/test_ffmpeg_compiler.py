import sys
import os
import structlog
import subprocess
import time
from pathlib import Path
from typing import List

# Windows Unicode sorunları için
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.core.hustler.domain.models.template import TemplateSpec, RenderConfig, SafeZone
from services.core.hustler.generators.ffmpeg_compiler import FFmpegCompiler

logger = structlog.get_logger()

def assert_compiles(cmd: List[str], ass_path: str) -> None:
    """
    K-603 Kuru Çalıştırma (Dry Run) Yardımcısı:
    Fiziksel disk işlemlerini (I/O) atlayarak FFmpeg derleme grafını (DAG) sanal girdiler ve çıktılarla doğrular.
    """
    # 1. ASS filtresinin çökmemesi için geçici asgari bir ASS dosyası oluştur
    ass_file = Path(ass_path)
    ass_file.parent.mkdir(exist_ok=True, parents=True)
    ass_file.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n[V4+ Styles]\nStyle: Default,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n[Events]\nDialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Kuru Calistirma\n", encoding="utf-8")
    
    # 2. Komutu Sanal Girdiler (Lavfi) ve Null Çıktı ile Değiştir
    dry_cmd = []
    i = 0
    while i < len(cmd):
        if cmd[i] == "-i":
            input_file = cmd[i+1]
            # Fiziksel girdileri sanal (lavfi) kaynaklarla değiştir
            if input_file.endswith(".mp4"):
                # 0.1 saniyelik siyah video
                dry_cmd.extend(["-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=0.1"])
            elif input_file.endswith(".mp3"):
                # 0.1 saniyelik sessizlik
                dry_cmd.extend(["-f", "lavfi", "-i", "aevalsrc=0:d=0.1"])
            else:
                dry_cmd.extend(["-i", input_file])
            i += 2
        elif i == len(cmd) - 1:
            # Çıktıyı null muxer'a gönder (Hiçliğe yaz). Sadece 1 kare işleyip çıkması için -frames:v 1 ekle.
            dry_cmd.extend(["-frames:v", "1", "-f", "null", "NUL" if os.name == "nt" else "-"])
            i += 1
        else:
            dry_cmd.append(cmd[i])
            i += 1

    # 3. Kuru Çalıştırmayı Tetikle
    logger.info(">>> KURU ÇALIŞTIRMA (DRY RUN) BAŞLATILIYOR <<<")
    logger.debug("Sanal Komut Dizilimi", cmd=" ".join(dry_cmd))
    
    start_time = time.time()
    try:
        # Sadece komutun başarılı yürütülmesini test ediyoruz, I/O olmadığı için hemen dönmeli
        result = subprocess.run(
            dry_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=True
        )
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Sürenin aşırı kısa (ms cinsinden) olduğunu doğrula
        assert elapsed_ms < 2000, f"Kuru çalıştırma çok uzun sürdü ({elapsed_ms}ms)! Disk I/O sızıntısı olabilir."
        
        logger.info("✅ KURU ÇALIŞTIRMA BAŞARILI: FFmpeg Filter Complex Grafı Onaylandı!", sure_ms=round(elapsed_ms, 2))
        
    except subprocess.CalledProcessError as e:
        logger.error("❌ KURU ÇALIŞTIRMA ÇÖKTÜ: Filter Graph Geçersiz!", hata_kodu=e.returncode)
        logger.error("FFmpeg Stderr Logları", log=e.stderr)
        raise e
    finally:
        if ass_file.exists():
            ass_file.unlink()

def main() -> None:
    logger.info("--- M6 K-603: FFMPEG DERLEYİCİ MİMARİ STANDART (DRY RUN) TESTİ ---")
    
    template = TemplateSpec(
        name="Mimari Test Şablonu",
        target_duration_sec=30,
        max_scenes=5,
        allowed_tones=["didaktik"],
        render_config=RenderConfig(
            width=1080,
            height=1920,
            fps=30,
            bg_color="#000000",
            safe_zone=SafeZone(
                margin_top=200, margin_bottom=200, margin_left=50, margin_right=50
            )
        )
    )
    
    # Gerçekte var olmayan sentetik yollar (Kuru çalıştırmada fiziksel dosyaya ihtiyaç yok)
    assets = [r"C:\sanal\dummy_scene1.mp4", r"C:\sanal\dummy_scene2.mp4"]
    audio_path = r"C:\sanal\dummy_audio.mp3"
    ass_path = r"test_assets\sanal_altyazi.ass" # Geçici dosya oluşturulacağı için erişilebilir yol
    bg_music_path = r"C:\sanal\dummy_bg.mp3"
    output_path = r"C:\sanal\output_final.mp4"
    
    # Komutu İnşa Et
    cmd = FFmpegCompiler.build_render_command(
        template=template,
        audio_path=audio_path,
        ass_path=ass_path,
        assets=assets,
        output_path=output_path,
        bg_music_path=bg_music_path
    )
    
    cmd_str = " ".join(cmd)
    logger.info("Üretilen Gerçek Komut", komut=cmd_str)
    
    # assert_compiles ile donanımsal (I/O) yük olmadan saf graf (DAG) testini yap
    assert_compiles(cmd, ass_path)
    
    logger.info("--- K-603 MİMARİ STANDART TESTİ TAMAMLANDI ---")

if __name__ == '__main__':
    main()
