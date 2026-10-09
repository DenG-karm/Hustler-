from pydantic import BaseModel, Field, field_validator
from typing import List

class SafeZone(BaseModel):
    margin_top: int = Field(..., description="Üst güvenlik marjı (piksel)")
    margin_bottom: int = Field(..., description="Alt güvenlik marjı (piksel)")
    margin_left: int = Field(..., description="Sol güvenlik marjı (piksel)")
    margin_right: int = Field(..., description="Sağ güvenlik marjı (piksel)")

class RenderConfig(BaseModel):
    width: int
    height: int
    fps: int
    bg_color: str = Field(..., description="Arka plan rengi (HEX)")
    safe_zone: SafeZone

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        if v != 1080:
            raise ValueError("Sistem sadece dikey format destekler (width=1080)")
        return v

    @field_validator("height")
    @classmethod
    def validate_height(cls, v: int) -> int:
        if v != 1920:
            raise ValueError("Sistem sadece dikey format destekler (height=1920)")
        return v

    @field_validator("fps")
    @classmethod
    def validate_fps(cls, v: int) -> int:
        if v != 30:
            raise ValueError("Sistem sadece 30 FPS destekler")
        return v

class TemplateSpec(BaseModel):
    """
    K-402: TemplateSpec Sözleşmesi
    Senaryoların uyması gereken katı şablon kurallarını tanımlar.
    Varsayılan (default) değerlere veya esnek (Any) tiplere asla izin verilmez.
    """
    name: str = Field(
        ..., 
        min_length=3,
        description="Şablonun adı (En az 3 karakter olmalıdır)."
    )
    target_duration_sec: int = Field(
        ..., 
        ge=15, 
        le=180, 
        description="Hedeflenen video süresi (15 saniye ile 180 saniye arasında olmalıdır)."
    )
    max_scenes: int = Field(
        ..., 
        ge=1, 
        le=10, 
        description="Senaryodaki maksimum sahne sayısı (1 ile 10 arasında olmalıdır)."
    )
    allowed_tones: List[str] = Field(
        ..., 
        min_length=1, 
        description="Kabul edilen anlatım tonları listesi (En az 1 ton içermelidir)."
    )
    render_config: RenderConfig
