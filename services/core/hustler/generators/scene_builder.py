from enum import Enum
from typing import Dict
from services.core.hustler.generators.ffmpeg_ast import Filter, FilterChain
from services.core.hustler.domain.models.profile import RenderProfile

class MotionType(Enum):
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_RIGHT = "pan_right"
    PAN_LEFT = "pan_left"

class MotionRegistry:
    @staticmethod
    def get_formula(motion: MotionType, duration_sec: float, fps: int = 30) -> Dict[str, str]:
        frames = int(duration_sec * fps)
        formulas = {
            MotionType.ZOOM_IN: {"z": "'min(zoom+0.0015,1.5)'", "x": "'iw/2-(iw/zoom/2)'", "y": "'ih/2-(ih/zoom/2)'"},
            MotionType.ZOOM_OUT: {"z": "'if(eq(on,1),1.5,zoom-0.0015)'", "x": "'iw/2-(iw/zoom/2)'", "y": "'ih/2-(ih/zoom/2)'"},
            MotionType.PAN_RIGHT: {"z": "1.1", "x": "'min(x+1,iw-iw/zoom)'", "y": "'ih/2-(ih/zoom/2)'"},
            MotionType.PAN_LEFT: {"z": "1.1", "x": "'max((iw-iw/zoom)-on*1,0)'", "y": "'ih/2-(ih/zoom/2)'"}
        }
        base = formulas[motion]
        base["d"] = str(frames)
        base["s"] = "1080x1920"
        base["fps"] = str(fps)
        return base

class SceneClipBuilder:
    def __init__(self, target_width: int = 1080, target_height: int = 1920, target_fps: int = 30) -> None:
        self.width = target_width
        self.height = target_height
        self.fps = target_fps
        self._motion_idx = 0
        self._motions = list(MotionType)

    def _get_next_motion(self) -> MotionType:
        m = self._motions[self._motion_idx % len(self._motions)]
        self._motion_idx += 1
        return m

    def build_clip_chain(self, asset_path: str, is_video: bool, duration: float, profile: RenderProfile = RenderProfile.FINAL) -> FilterChain:
        w = self.width
        h = self.height
        
        if profile == RenderProfile.DRAFT:
            # Çözünürlüğü düşür
            w = 540
            h = 960
            
        scale_filter = Filter("scale", args=[f"{w}", f"{h}"], kwargs={"force_original_aspect_ratio": "increase"})
        crop_filter = Filter("crop", args=[f"{w}", f"{h}"], kwargs={})
        setsar_filter = Filter("setsar", args=["1"], kwargs={})
        fps_filter = Filter("fps", args=[f"{self.fps}"], kwargs={})
        
        filters = [scale_filter, crop_filter, setsar_filter, fps_filter]
        
        if not is_video and profile == RenderProfile.FINAL:
            # Sadece FINAL profilde animasyon ekle
            motion = self._get_next_motion()
            params = MotionRegistry.get_formula(motion, duration, self.fps)
            # DRAFT için s argümanı formülde 1080x1920'ye sabitlendiğinden, DRAFT ise hiç girmeyiz.
            zoompan_filter = Filter("zoompan", args=[], kwargs=params)
            filters.append(zoompan_filter)
            
        return FilterChain(filters)
