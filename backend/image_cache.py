from sqlalchemy.orm import Session
from .models import ImageCache
from .config import settings
import os
import aiofiles
import logging

logger = logging.getLogger(__name__)

async def get_cached_image(db: Session, image_hash: str):
    if not settings.CACHE_ENABLED:
        return None
    cache_entry = db.query(ImageCache).filter(ImageCache.image_hash == image_hash).first()
    if cache_entry and os.path.exists(cache_entry.file_path):
        async with aiofiles.open(cache_entry.file_path, 'rb') as f:
            return await f.read()
    return None

async def save_cached_image(db: Session, image_hash: str, image_bytes: bytes) -> str:
    if not settings.CACHE_ENABLED:
        return ""
    
    file_path = os.path.join(settings.OUTPUTS_DIR, f"{image_hash}.png")
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(image_bytes)
        
    cache_entry = db.query(ImageCache).filter(ImageCache.image_hash == image_hash).first()
    if not cache_entry:
        cache_entry = ImageCache(image_hash=image_hash, file_path=file_path)
        db.add(cache_entry)
        db.commit()
    
    return file_path
