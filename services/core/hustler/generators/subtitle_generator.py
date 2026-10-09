from typing import List
from pydantic import BaseModel, Field

from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming

class SubtitleStyle(BaseModel):
    """
    ASS (Advanced SubStation Alpha) Altyazı Stil Kısıtları.
    Renkler her zaman &HBBGGRR& (Blue-Green-Red) formatında olmalıdır.
    """
    font_name: str = Field("Arial", description="Kullanılacak Font (Sistemde veya projede yüklü olmalıdır).")
    font_size: int = Field(90, description="Font boyutu.")
    primary_color: str = Field("&H00FFFFFF&", description="Ana metin rengi (Varsayılan: Beyaz).")
    highlight_color: str = Field("&H0000FFFF&", description="Vurgu rengi (Varsayılan: Sarı).")
    alignment: int = Field(5, description="Ekranda hizalama (5 = Tam Merkez, 2 = Alt Merkez).")
    margin_v: int = Field(50, description="Dikey eksendeki kenar boşluğu.")

class AssDocument:
    """
    K-503: AssDocument Jeneratörü
    Milisaniye cinsindeki kelime zamanlamalarını (WordTiming) alır ve 
    FFMPEG'in yakarak (burn-in) videoya basacağı formatlı .ass dosyası içeriğini üretir.
    """
    
    @staticmethod
    def ms_to_ass_time(ms: int) -> str:
        """
        Milisaniye değerini ASS zaman formatına (H:MM:SS.cs) çevirir.
        cs = centisecond (saniyenin yüzde biri, 2 hane).
        Örnek: 1900 ms -> 0:00:01.90
        """
        if ms < 0:
            raise ValueError(f"Negatif zaman damgası geçersiz: {ms} ms")
        total_seconds = ms / 1000.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        centiseconds = int(round((total_seconds - int(total_seconds)) * 100))
        
        # Yuvarlama taşmalarını (100 cs = 1 saniye) düzelt
        if centiseconds >= 100:
            centiseconds = 0
            seconds += 1
            if seconds >= 60:
                seconds = 0
                minutes += 1
                if minutes >= 60:
                    minutes = 0
                    hours += 1
                    
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    @classmethod
    def generate(cls, words: List[WordTiming], style: SubtitleStyle) -> str:
        """
        Gerekli başlıkları ve zamanlanmış kelimeleri içeren nihai .ass metnini üretir.
        """
        # --- ASS DOSYA BAŞLIKLARI (HEADER) ---
        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "WrapStyle: 1\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{style.font_name},{style.font_size},{style.primary_color},&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,2,0,{style.alignment},10,10,{style.margin_v},1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        
        # --- ZAMANLANMIŞ DİYALOGLAR (EVENTS) ---
        events = []
        for w in words:
            start_str = cls.ms_to_ass_time(w.start_ms)
            end_str = cls.ms_to_ass_time(w.end_ms)
            
            # Kelime Vurgusu: ASS renk değiştirme etiketi {\c&H...&}
            # Shorts stiline uygun olarak ekranda kelime kelime vurgulama yapıyoruz
            text_with_fx = f"{{\\c{style.highlight_color}}}{w.word}"
            
            dialogue_line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_with_fx}"
            events.append(dialogue_line)
            
        return header + "\n".join(events) + "\n"
