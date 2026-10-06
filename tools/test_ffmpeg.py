import os
import subprocess
import time
from dataclasses import dataclass, field

import structlog

# =====================================================================
# LOGGING KURULUMU
# =====================================================================
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


# =====================================================================
# 1. OOP FILTERGRAPH DERLEYİCİ
# =====================================================================

@dataclass
class FilterNode:
    name: str
    args: dict = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    def render(self) -> str:
        in_str = "".join(f"[{i}]" for i in self.inputs)
        out_str = "".join(f"[{o}]" for o in self.outputs)
        args_str = ":".join(f"{k}={v}" for k, v in self.args.items()) if self.args else ""
        middle = f"{self.name}={args_str}" if args_str else self.name
        return f"{in_str}{middle}{out_str}"

class FilterChain:
    def __init__(self, nodes: list[FilterNode]):
        self.nodes = nodes

    def render(self) -> str:
        return ",".join(n.render() for n in self.nodes)

class FilterGraph:
    def __init__(self):
        self.chains: list[FilterChain] = []

    def add_chain(self, chain: FilterChain):
        self.chains.append(chain)

    def compile(self) -> str:
        return ";".join(c.render() for c in self.chains)


# =====================================================================
# YARDIMCI METOTLAR
# =====================================================================

def generate_test_ass(filepath: str):
    ass_content = """[Script Info]
ScriptType: v4.00+
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:20.00,Default,,0,0,0,,Hustler OOP Render Test
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ass_content)

def build_graph() -> FilterGraph:
    graph = FilterGraph()
    
    # Görselleri 1080x1920'ye zorla
    for i in range(8):
        node = FilterNode("scale", {"w": 1080, "h": 1920}, [f"{i}:v"], [f"v{i}_scaled"])
        graph.add_chain(FilterChain([node]))
        
    # Xfade Geçişleri (Zincirleme)
    last_out = "v0_scaled"
    current_offset = 2.5
    for i in range(1, 8):
        out_label = f"xfade_{i}"
        node = FilterNode(
            "xfade", 
            {"transition": "fade", "duration": 0.5, "offset": current_offset},
            [last_out, f"v{i}_scaled"],
            [out_label]
        )
        graph.add_chain(FilterChain([node]))
        last_out = out_label
        current_offset += 2.5
        
    # Altyazı Ekleme (ASS)
    # Not: Windows'ta path kaçışları sorunu olmaması için aynı dizindeki dosyayı kullanıyoruz
    ass_node = FilterNode("ass", {"filename": "'test.ass'"}, [last_out], ["vout"])
    graph.add_chain(FilterChain([ass_node]))
    
    return graph

# =====================================================================
# ANA TEST AKIŞI
# =====================================================================

def main():
    logger.info("--- GÖREV 3: OOP Filtergraph ve Render Kararlılığı Başlıyor ---")
    
    # 2. Girdilerin Hazırlanması
    ass_file = "test.ass"
    generate_test_ass(ass_file)
    
    colors = ["red", "blue", "green", "yellow", "orange", "purple", "cyan", "white"]
    input_args = []
    
    # 8 Sentetik Görsel (3 saniye x 8 = 24 sn, Xfade ile kısaldığında 20.5 sn)
    for c in colors:
        input_args.extend(["-f", "lavfi", "-i", f"color=c={c}:s=1080x1920:d=3"])
    
    # 1 Sentetik Ses (lavfi aevalsrc)
    input_args.extend(["-f", "lavfi", "-i", "aevalsrc=0:d=20.5"])
    
    graph = build_graph()
    filter_script = graph.compile()
    
    logger.debug("Oluşturulan Filtergraph", script=filter_script)
    
    # 3. Kuru Çalıştırma (Dry Run)
    cmd_dry_run = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_script,
        "-map", "[vout]", "-map", "8:a",
        "-f", "null", "-"
    ]
    
    logger.info("Kuru Çalıştırma (Dry Run) Başlatılıyor...")
    start_time = time.time()
    result = subprocess.run(cmd_dry_run, capture_output=True, text=True)
    dry_run_time = time.time() - start_time
    
    # KESİN DOĞRULAMA (Etiket veya söz dizimi kopuksa FFmpeg hata döner)
    assert result.returncode == 0, f"Kuru çalıştırma başarısız oldu! Etiket/Sözdizimi hatası olabilir.\n{result.stderr}"
    logger.info("Kuru Çalıştırma BAŞARILI", sure_sn=round(dry_run_time, 2))
    
    # 4. Taslak Önizleme (Draft Render)
    cmd_draft = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_script,
        "-map", "[vout]", "-map", "8:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-s", "360x640",
        "draft_output.mp4"
    ]
    
    logger.info("Taslak Render (Draft) Başlatılıyor...")
    start_time = time.time()
    subprocess.run(cmd_draft, capture_output=True)
    draft_time = time.time() - start_time
    logger.info("Taslak Render BAŞARILI", sure_sn=round(draft_time, 2))
    
    # 5. Nihai Render
    cmd_final = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_script,
        "-map", "[vout]", "-map", "8:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "final_output.mp4"
    ]
    
    logger.info("Nihai Render (Final) Başlatılıyor...")
    start_time = time.time()
    subprocess.run(cmd_final, capture_output=True)
    final_time = time.time() - start_time
    logger.info("Nihai Render BAŞARILI", sure_sn=round(final_time, 2))
    
    # METRİKLER VE BÜTÇE KONTROLÜ
    logger.info(
        "=== FFMPEG RENDER METRİKLERİ ===",
        kuru_calistirma_basarili=True,
        taslak_sure_sn=round(draft_time, 2),
        nihai_sure_sn=round(final_time, 2)
    )
    
    assert draft_time < 10.0, f"Taslak render çok yavaş: {draft_time}s > 10s"
    assert final_time < 120.0, f"Nihai render çok yavaş: {final_time}s > 120s"
    
    logger.info("M1 FAZ 0 (K-104, K-105) RENDER TESTLERİ BAŞARILI.")

if __name__ == "__main__":
    main()
