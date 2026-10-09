from typing import List, Tuple
from services.core.hustler.generators.ffmpeg_ast import Filter
from services.core.hustler.domain.models.profile import RenderProfile

class TransitionPlanner:
    """
    Kliplerin birleştirilirken uygulanacak xfade (crossfade) geçişlerinin
    süre örtüşmelerini hesaplar ve FFmpeg AST grafını inşa eder.
    """
    @staticmethod
    def calculate_offsets(durations: List[float], transition_sec: float) -> List[float]:
        offsets = []
        current_time = 0.0
        
        for i in range(len(durations) - 1):
            if i == 0:
                current_time = durations[0]
            else:
                current_time += durations[i] - transition_sec
                
            offset = current_time - transition_sec
            offsets.append(offset)
            
        return offsets

    @staticmethod
    def build_graph(stream_labels: List[str], durations: List[float], transition_sec: float, profile: RenderProfile = RenderProfile.FINAL) -> Tuple[List[str], str]:
        if not stream_labels or len(stream_labels) != len(durations):
            raise ValueError("Etiketler ve süreler eşleşmelidir.")
            
        if len(stream_labels) == 1:
            return [], stream_labels[0]
            
        if profile == RenderProfile.DRAFT:
            # DRAFT profilinde ağır xfade atlanır, basit concat yapılır
            out_label = "concat_v"
            inputs = "".join([f"[{lbl}]" for lbl in stream_labels])
            line = f"{inputs}concat=n={len(stream_labels)}:v=1:a=0[{out_label}]"
            return [line], out_label
            
        offsets = TransitionPlanner.calculate_offsets(durations, transition_sec)
        graph_lines = []
        current_out = stream_labels[0]
        
        for i, offset in enumerate(offsets):
            next_in = stream_labels[i + 1]
            out_label = f"xfade{i}"
            
            f = Filter("xfade", args=[], kwargs={
                "transition": "fade",
                "duration": str(transition_sec),
                "offset": f"{offset:.3f}"
            })
            
            line = f"[{current_out}][{next_in}]{f.to_string()}[{out_label}]"
            graph_lines.append(line)
            current_out = out_label
            
        return graph_lines, current_out
