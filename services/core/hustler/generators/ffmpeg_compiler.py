from typing import List, Optional
from services.core.hustler.domain.models.template import TemplateSpec

class FFmpegCompiler:
    """
    M6 K-603: FFmpeg Derleyici (Compiler)
    TemplateSpec üzerindeki katı kuralları (çözünürlük, fps vb.) baz alarak,
    saf, deterministik ve çalıştırılabilir bir FFmpeg komut dizisi üretir.
    I/O (subprocess) içermez, sadece komutu inşa eder.
    """
    
    @staticmethod
    def _escape_ass_path(path: str) -> str:
        """Windows yollarını FFmpeg ass filtresine uyacak şekilde kaçar (escape)."""
        # Ters bölüleri düz bölüye çevir
        p = path.replace("\\", "/")
        # Sürücü harflerindeki iki noktayı kaç (Örn: C:/ -> C\:/)
        p = p.replace(":", "\\:")
        return p

    @staticmethod
    def build_render_command(
        template: TemplateSpec, 
        audio_path: str, 
        ass_path: str, 
        assets: List[str], 
        output_path: str,
        bg_music_path: Optional[str] = None
    ) -> List[str]:
        if not assets:
            raise ValueError("En az bir görsel asset (video/resim) verilmelidir.")
            
        cmd = ["ffmpeg", "-y"]
        
        # 1. Girdileri Ekle (Inputs)
        for asset in assets:
            cmd.extend(["-i", asset])
            
        tts_idx = len(assets)
        cmd.extend(["-i", audio_path])
        
        bg_idx = -1
        if bg_music_path:
            bg_idx = len(assets) + 1
            cmd.extend(["-i", bg_music_path])
            
        # 2. Filtre Kompleksini (Filter Complex) İnşa Et
        filters = []
        concat_inputs = ""
        width = template.render_config.width
        height = template.render_config.height
        fps = template.render_config.fps
        
        # Görselleri normalize et (Center Crop, Scale, FPS)
        for i in range(len(assets)):
            # force_original_aspect_ratio=increase ile boşluk kalmamasını sağla, sonra crop ile ortala
            scale_crop = f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}[v{i}]"
            filters.append(scale_crop)
            concat_inputs += f"[v{i}]"
            
        # Parçaları birleştir
        if len(assets) > 1:
            filters.append(f"{concat_inputs}concat=n={len(assets)}:v=1:a=0[concat_v]")
            current_v = "[concat_v]"
        else:
            current_v = "[v0]"
            
        # Altyazıyı göm (Burn-in)
        escaped_ass = FFmpegCompiler._escape_ass_path(ass_path)
        filters.append(f"{current_v}ass='{escaped_ass}'[out_v]")
        
        # Ses Miksajı (Audio Mixing)
        audio_map = ""
        if bg_music_path:
            # Arka plan müziğinin sesini -20dB (yaklaşık %10 volume) kıs
            filters.append(f"[{bg_idx}:a]volume=0.1[bg_a]")
            # TTS sesi ile kısık arka plan sesini birleştir
            filters.append(f"[{tts_idx}:a][bg_a]amix=inputs=2:duration=first:dropout_transition=2[out_a]")
            audio_map = "[out_a]"
        else:
            # Doğrudan TTS sesini kullan
            audio_map = f"{tts_idx}:a"
            
        filter_complex_str = ";".join(filters)
        
        # 3. Komutu Birleştir
        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[out_v]",
            "-map", audio_map,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ])
        
        return cmd
