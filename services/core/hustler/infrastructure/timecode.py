from typing import Any
import structlog

logger = structlog.get_logger()

class TimeCode:
    """
    K-505: Ses ve Görüntü senkronizasyonu için katı zaman hesaplayıcısı.
    Zaman (ms) -> Kare (Frame) -> Zaman (ms) dönüşümlerini yönetir.
    Sistem varsayılan olarak Shorts/Reels standartı olan 30 FPS üzerinden çalışır.
    """
    FPS = 30
    
    @classmethod
    def ms_to_frames(cls, ms: int) -> int:
        """Milisaniyeyi (ms) tam sayı olarak çerçeve (frame) sayısına dönüştürür."""
        # Frame = (ms * FPS) / 1000
        # Hassasiyet kaybolmaması için en yakın tamsayıya yuvarlanır.
        return int(round((ms * cls.FPS) / 1000.0))
        
    @classmethod
    def frames_to_ms(cls, frames: int) -> int:
        """Çerçeve (frame) sayısını tamsayı olarak milisaniyeye (ms) dönüştürür."""
        return int(round((frames * 1000.0) / cls.FPS))

class SceneSynchronizer:
    """
    Sahnelerin ekranda kalma sürelerini (Duration) ses dosyasıyla kare kare (frame-by-frame)
    eşleştirir. Video ile sesin kaymasını engellemek için Artık Yönetimi (Drift Prevention) uygular.
    """
    @staticmethod
    def sync_scenes(total_audio_ms: int, scene_count: int) -> list[dict[str, Any]]:
        """
        Toplam sesi sahnelere eşit böler.
        Bölme işleminden artan küsuratlı kareleri (remainder) yok etmek yerine
        sahnelere 1'er kare dağıtarak toplam senkronizasyonu kilitler.
        """
        if scene_count <= 0:
            return []
            
        total_frames = TimeCode.ms_to_frames(total_audio_ms)
        
        # Tam bölünen kısım ve arta kalan (remainder) kareler
        base_frames_per_scene = total_frames // scene_count
        remainder_frames = total_frames % scene_count
        
        scenes = []
        current_start_frame = 0
        
        for i in range(scene_count):
            # Artık kareleri (remainder) kaybetmemek için baştaki sahnelere 1'er kare ekle
            added_frame = 1 if i < remainder_frames else 0
            scene_frames = base_frames_per_scene + added_frame
            
            start_ms = TimeCode.frames_to_ms(current_start_frame)
            duration_ms = TimeCode.frames_to_ms(scene_frames)
            
            scenes.append({
                "scene_index": i,
                "frames": scene_frames,
                "start_ms": start_ms,
                "duration_ms": duration_ms
            })
            
            current_start_frame += scene_frames
            
        return scenes
