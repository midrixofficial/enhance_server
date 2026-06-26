from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
import uuid
import base64
import logging
from typing import Optional
from io import BytesIO
from PIL import Image

from .database import get_db
from .models import Job
from .schemas import EnhanceJobResponse, JobStatusResponse
from .config import settings
from .utils import get_image_hash
from .image_cache import get_cached_image
from .runpod_client import runpod_client
from .job_manager import job_manager

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_user_id(x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header missing")
    return x_user_id

@router.post("/enhance", response_model=EnhanceJobResponse)
async def enhance_image(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    sharpen_amount: Optional[float] = Form(None),
    contrast_alpha: Optional[float] = Form(None),
    brightness_beta: Optional[float] = Form(None),
    tile_size: Optional[int] = Form(None),
    tile_pad: Optional[int] = Form(None),
    output_format: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db)
):
    if image.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image format")
        
    image_bytes = await image.read()
    if len(image_bytes) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
        
    image_hash = get_image_hash(image_bytes)
    
    # Check Cache
    cached_image = await get_cached_image(db, image_hash)
    if cached_image:
        logger.info(f"Cache hit for hash {image_hash}")
        return EnhanceJobResponse(job_id=f"cache_{image_hash}", status="COMPLETED")
        
    # Check Active Job
    active_job = db.query(Job).filter(
        Job.user_id == user_id,
        Job.status.in_(["QUEUED", "IN_PROGRESS"])
    ).first()
    
    if active_job:
        logger.info(f"User {user_id} already has active job {active_job.job_id}")
        return EnhanceJobResponse(job_id=active_job.job_id, status=active_job.status)
        
    # Concurrency limit check
    active_jobs_count = db.query(Job).filter(Job.status.in_(["QUEUED", "IN_PROGRESS"])).count()
    if active_jobs_count >= settings.MAX_CONCURRENT_RUNPOD_JOBS:
        raise HTTPException(status_code=429, detail="Too many concurrent jobs")
        
    # Submit to RunPod
    try:
        input_data = {
            "image": base64.b64encode(image_bytes).decode('utf-8'),
            "sharpen_amount": sharpen_amount,
            "contrast_alpha": contrast_alpha,
            "brightness_beta": brightness_beta,
            "tile_size": tile_size,
            "tile_pad": tile_pad,
            "output_format": output_format
        }
        input_data = {k: v for k, v in input_data.items() if v is not None}
        
        runpod_job_id = await runpod_client.submit_job(input_data)
        internal_job_id = str(uuid.uuid4())
        
        new_job = Job(
            job_id=internal_job_id,
            user_id=user_id,
            image_hash=image_hash,
            status="QUEUED",
            runpod_job_id=runpod_job_id
        )
        db.add(new_job)
        db.commit()
        
        background_tasks.add_task(job_manager.poll_job, internal_job_id, runpod_job_id, image_hash)
        
        return EnhanceJobResponse(job_id=internal_job_id, status="QUEUED")
        
    except Exception as e:
        logger.exception("Failed to submit job: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    if job_id.startswith("cache_"):
        image_hash = job_id.replace("cache_", "")
        cached_result = await get_cached_image(db, image_hash)
        if cached_result:
            try:
                img = Image.open(BytesIO(cached_result))
                width, height = img.size
            except Exception:
                width, height = None, None
                
            return JobStatusResponse(
                status="COMPLETED",
                image_base64=base64.b64encode(cached_result).decode('utf-8'),
                width=width,
                height=height
            )
            
    db_job = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if db_job.status == "COMPLETED":
        cached_result = await get_cached_image(db, db_job.image_hash)
        if cached_result:
            try:
                img = Image.open(BytesIO(cached_result))
                width, height = img.size
            except Exception:
                width, height = None, None
                
            return JobStatusResponse(
                status="COMPLETED",
                image_base64=base64.b64encode(cached_result).decode('utf-8'),
                width=width,
                height=height
            )
            
    return JobStatusResponse(status=db_job.status)
