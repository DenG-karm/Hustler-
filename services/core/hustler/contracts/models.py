from pydantic import BaseModel, Field

from services.core.hustler.domain.models.script import ScriptDoc
from services.core.hustler.domain.models.template import (
    AssetType,
    RecoveryStrategy,
    RenderConfig,
    SafeZone,
    SlotSpec,
    TemplateSpec,
)
from services.core.hustler.generators.subtitle_generator import SubtitleStyle
from services.core.hustler.infrastructure.timestamp_normalizer import WordTiming
from services.core.hustler.validation.claims import ClaimReport

class VideoRecord(BaseModel):
    id: str = Field(..., description="Unique video identifier")
    title: str = Field(..., description="Title of the video")
    duration: int = Field(..., description="Duration in seconds")

__all__ = [
    "VideoRecord",
    "ScriptDoc",
    "TemplateSpec",
    "RenderConfig",
    "SafeZone",
    "SlotSpec",
    "RecoveryStrategy",
    "AssetType",
    "SubtitleStyle",
    "WordTiming",
    "ClaimReport",
]
