from pydantic import BaseModel
from typing import Optional

class EnhanceJobResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    status: str
    image_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None

class EnhanceParams(BaseModel):
    sharpen_amount: Optional[float] = None
    contrast_alpha: Optional[float] = None
    brightness_beta: Optional[float] = None
    tile_size: Optional[int] = None
    tile_pad: Optional[int] = None
    output_format: Optional[str] = None
