import sys
import os
import structlog

if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding.lower() != 'utf-8':
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding.lower() != 'utf-8':
    getattr(sys.stderr, 'reconfigure')(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.generators.graph_validator import GraphValidator
from services.core.hustler.generators.scene_builder import SceneClipBuilder
from services.core.hustler.generators.transition_planner import TransitionPlanner
from services.core.hustler.generators.audio_mixer import AudioMixer
from tools.smoke.smoke_ffmpeg_compiler import assert_compiles

logger = structlog.get_logger()

def main() -> None:
    logger.info("--- M6 K-606: GRAPH VALIDATOR VE RENDER PROFILLERI TESTİ ---")
    
    # 1. İhlal Testi (Kopuk Etiket)
    logger.info(">>> TEST 1: İhlal Testi (Kopuk Etiket Yakalama) <<<")
    bad_graph = [
        "[0:v]scale=1080:1920[v0]",
        "[1:v]scale=1080:1920[v1]",
        "[v0][v1]concat=n=2:v=1:a=0[out_v]",
        # v2 üretiliyor ama hiçbir map argümanı veya başka filtre tarafından tüketilmiyor (KOPUK)
        "[2:v]scale=1080:1920[v2]"
    ]
    map_args = ["[out_v]"]
    
    try:
        GraphValidator.validate_graph(bad_graph, map_args)
        assert False, "Hata fırlatılmadı, validasyon başarısız!"
    except ValueError as e:
        logger.info("✅ İhlal başarıyla yakalandı!", hata_mesaji=str(e))
        
    # 2. DRAFT Profil Testi
    logger.info(">>> TEST 2: DRAFT Profil AST İnşası ve Dry Run <<<")
    profile = RenderProfile.DRAFT
    
    builder = SceneClipBuilder()
    # DRAFT olduğu için çözünürlük düşecek ve resim animasyonu eklenmeyecek
    chain1 = builder.build_clip_chain("dummy1.mp4", True, 5.0, profile)
    chain2 = builder.build_clip_chain("dummy2.jpg", False, 4.0, profile)
    
    graph_lines = [
        f"[0:v]{chain1.to_string()}[v0]",
        f"[1:v]{chain2.to_string()}[v1]"
    ]
    
    # DRAFT olduğu için xfade yerine basit concat kullanılacak
    xfade_lines, final_v = TransitionPlanner.build_graph(["v0", "v1"], [5.0, 4.0], 0.5, profile)
    graph_lines.extend(xfade_lines)
    
    # DRAFT olduğu için loudnorm kullanılmayacak, doğrudan amix (eğer bg varsa)
    audio_lines, final_a = AudioMixer.build_mix_graph("2:a", "3:a", profile)
    graph_lines.extend(audio_lines)
    
    # Graf Topolojik Olarak Geçerli mi?
    GraphValidator.validate_graph(graph_lines, [f"[{final_v}]", f"[{final_a}]"])
    logger.info("✅ DRAFT AST Grafı topolojik olarak kusursuz, kural ihlali yok!")
    logger.info("Üretilen Graf", graf=graph_lines)
    
    # Kuru Çalıştırma (Dry-Run)
    filter_complex = ";".join(graph_lines)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=540x960:d=5",
        "-f", "lavfi", "-i", "color=c=blue:s=540x960:d=4",
        "-f", "lavfi", "-i", "aevalsrc=0:d=10",
        "-f", "lavfi", "-i", "aevalsrc=0:d=10",
        "-filter_complex", filter_complex,
        "-map", f"[{final_v}]",
        "-map", f"[{final_a}]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "output.mp4"
    ]
    
    logger.info("DRAFT Dry-Run Öncesi Hazırlanan Komut", komut=" ".join(cmd))
    assert_compiles(cmd, "test_assets/dummy_sub.ass")
    
    logger.info("--- K-606 TESTİ BAŞARIYLA TAMAMLANDI ---")

if __name__ == '__main__':
    main()
