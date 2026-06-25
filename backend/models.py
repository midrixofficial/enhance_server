from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    image_hash = Column(String, index=True)
    status = Column(String) # QUEUED, IN_PROGRESS, COMPLETED, FAILED
    runpod_job_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ImageCache(Base):
    __tablename__ = "image_cache"

    id = Column(Integer, primary_key=True, index=True)
    image_hash = Column(String, unique=True, index=True)
    file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
