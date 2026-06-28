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
    if cache_entry:
        if os.path.exists(cache_entry.file_path):
            logger.info("Cache hit: Verified file exists at %s", cache_entry.file_path)
            return cache_entry.file_path
        else:
            logger.error("Cache miss: Database entry exists but file missing at %s", cache_entry.file_path)
    return None

async def save_cached_image(db: Session, image_hash: str, image_bytes: bytes) -> str:
    if not settings.CACHE_ENABLED:
        return ""
    
    logger.info("Ensuring output directory exists: %s", settings.OUTPUTS_DIR)
    os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
    file_path = os.path.join(settings.OUTPUTS_DIR, f"{image_hash}.jpg")
    
    logger.info("Saving enhanced image to %s", file_path)
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(image_bytes)
    except Exception as e:
        logger.exception("Failed to save image to %s", file_path)
        raise
        
    if not os.path.exists(file_path):
        logger.error("File existence check failed for %s", file_path)
        raise RuntimeError(f"Enhanced image was not saved: {file_path}")
        
    logger.info("Saved image successfully: %s", file_path)
        
    cache_entry = db.query(ImageCache).filter(ImageCache.image_hash == image_hash).first()
    if not cache_entry:
        cache_entry = ImageCache(image_hash=image_hash, file_path=file_path)
        db.add(cache_entry)
        db.commit()
    
    return file_path
