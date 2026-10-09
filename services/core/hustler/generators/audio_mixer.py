from typing import List, Tuple, Optional
from services.core.hustler.generators.ffmpeg_ast import Filter
from services.core.hustler.domain.models.profile import RenderProfile

class AudioMixer:
    """
    Sesleri endüstri standardına (loudnorm) göre eşitler ve 
    arka plan müziği ile TTS'i harmanlar.
    """
    @staticmethod
    def get_loudnorm_filter() -> Filter:
        return Filter("loudnorm", args=[], kwargs={
            "I": "-16",
            "TP": "-1.5",
            "LRA": "11"
        })
        
    @staticmethod
    def build_mix_graph(tts_label: str, bg_label: Optional[str] = None, profile: RenderProfile = RenderProfile.FINAL) -> Tuple[List[str], str]:
        graph_lines = []
        
        if profile == RenderProfile.DRAFT:
            # DRAFT'ta ağır loudnorm'lar atlanır
            tts_final = tts_label
            if not bg_label:
                return [], tts_label
            bg_vol_label = "bg_vol"
            graph_lines.append(f"[{bg_label}]volume=0.1[{bg_vol_label}]")
            out_label = "audio_out"
            amix = Filter("amix", args=[], kwargs={"inputs": "2", "duration": "first", "dropout_transition": "2"})
            graph_lines.append(f"[{tts_final}][{bg_vol_label}]{amix.to_string()}[{out_label}]")
            return graph_lines, out_label
            
        # FINAL Profili Standartları
        loudnorm = AudioMixer.get_loudnorm_filter()
        tts_norm_label = "tts_norm"
        graph_lines.append(f"[{tts_label}]{loudnorm.to_string()}[{tts_norm_label}]")
        
        if not bg_label:
            return graph_lines, tts_norm_label
            
        bg_norm_label = "bg_norm"
        graph_lines.append(f"[{bg_label}]{loudnorm.to_string()}[{bg_norm_label}]")
        
        bg_vol_label = "bg_vol"
        graph_lines.append(f"[{bg_norm_label}]volume=0.1[{bg_vol_label}]")
        
        out_label = "audio_out"
        amix = Filter("amix", args=[], kwargs={"inputs": "2", "duration": "first", "dropout_transition": "2"})
        graph_lines.append(f"[{tts_norm_label}][{bg_vol_label}]{amix.to_string()}[{out_label}]")
        
        return graph_lines, out_label
