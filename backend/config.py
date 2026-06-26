import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_ID: str = ""
    DATABASE_URL: str = "sqlite:///./enhancer.db"
    MAX_UPLOAD_MB: int = 20
    MAX_CONCURRENT_RUNPOD_JOBS: int = 2
    CACHE_ENABLED: bool = True
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]
    DEBUG: bool = False
    
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    UPLOADS_DIR: str = os.path.join(BASE_DIR, "uploads")
    OUTPUTS_DIR: str = os.path.join(BASE_DIR, "outputs")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
