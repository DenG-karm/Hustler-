from pydantic import BaseModel, Field

class VideoRecord(BaseModel):
    id: str = Field(..., description="Unique video identifier")
    title: str = Field(..., description="Title of the video")
    duration: int = Field(..., description="Duration in seconds")
