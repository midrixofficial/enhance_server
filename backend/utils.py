import hashlib
import os
import aiofiles
from .config import settings

def get_image_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()

async def save_upload_file(upload_file, file_name: str) -> str:
    file_path = os.path.join(settings.UPLOADS_DIR, file_name)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await upload_file.read()
        await out_file.write(content)
    return file_path

async def delete_file(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)
