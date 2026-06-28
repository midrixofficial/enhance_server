from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import uuid
import base64
import logging
import os
from typing import Optional
from io import BytesIO
from PIL import Image

from .database import get_db
from .models import Job
from .schemas import EnhanceJobResponse, JobStatusResponse
from .config import settings
from .utils import get_image_hash
from .image_cache import get_cached_image, save_cached_image
from .runpod_client import runpod_client

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_user_id(x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header missing")
    return x_user_id

@router.post("/enhance", response_model=EnhanceJobResponse)
async def enhance_image(
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
    image_bytes = await image.read()
    logger.info(
        "Upload received: filename=%s content_type=%s size=%d user=%s",
        image.filename,
        image.content_type,
        len(image_bytes),
        user_id
    )

    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
        logger.info(
            "Upload: filename=%s reported=%s detected=%s",
            image.filename,
            image.content_type,
            img.format
        )
    except Exception:
        logger.error(
            "Rejected upload: content_type=%s invalid image file",
            image.content_type
        )
        raise HTTPException(status_code=400, detail="Invalid image file")
        
    if len(image_bytes) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        logger.error(
            "Rejected upload: size=%d max=%d",
            len(image_bytes),
            settings.MAX_UPLOAD_MB * 1024 * 1024
        )
        raise HTTPException(status_code=400, detail="File too large")
        
    image_hash = get_image_hash(image_bytes)
    
    # Check Cache
    cached_image = await get_cached_image(db, image_hash)
    if cached_image:
        logger.info(f"Cache hit for hash {image_hash}")
        return EnhanceJobResponse(
            job_id=f"cache_{image_hash}", 
            status="COMPLETED"
        )
        
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
            "image_b64": base64.b64encode(image_bytes).decode('utf-8'),
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
        
        logger.info(f"RunPod submit successful. internal_id={internal_job_id}, runpod_id={runpod_job_id}")
        return EnhanceJobResponse(job_id=internal_job_id, status="QUEUED")
        
    except Exception as e:
        logger.exception("Failed to submit job: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, user_id: str = Depends(get_user_id), db: Session = Depends(get_db)):
    if job_id.startswith("cache_"):
        image_hash = job_id.replace("cache_", "")
        cached_result_path = await get_cached_image(db, image_hash)
        if cached_result_path:
            try:
                img = Image.open(cached_result_path)
                width, height = img.size
            except Exception:
                width, height = None, None
                
            filename = os.path.basename(cached_result_path)
            image_url = f"{settings.PUBLIC_IMAGE_BASE_URL}/{filename}"
            return JobStatusResponse(
                status="COMPLETED",
                image_url=image_url,
                width=width,
                height=height
            )
        else:
            raise HTTPException(status_code=404, detail="Cache entry not found")
            
    db_job = db.query(Job).filter(Job.job_id == job_id, Job.user_id == user_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if db_job.status == "COMPLETED":
        cached_result_path = await get_cached_image(db, db_job.image_hash)
        if cached_result_path:
            try:
                img = Image.open(cached_result_path)
                width, height = img.size
            except Exception:
                width, height = None, None
                
            filename = os.path.basename(cached_result_path)
            image_url = f"{settings.PUBLIC_IMAGE_BASE_URL}/{filename}"
            return JobStatusResponse(
                status="COMPLETED",
                image_url=image_url,
                width=width,
                height=height
            )
            
    # Poll RunPod live
    try:
        status_data = await runpod_client.check_job_status(db_job.runpod_job_id)
        current_status = status_data.get("status")
        logger.info(f"RunPod status for {db_job.runpod_job_id}: {current_status}")
        
        if current_status == "COMPLETED":
            logger.info(f"Job {db_job.runpod_job_id} completed. Caching result.")
            output = status_data.get("output", {})
            
            image_bytes = None
            if isinstance(output, str):
                image_bytes = base64.b64decode(output)
            elif isinstance(output, dict):
                image_b64 = output.get("image_b64") or output.get("image")
                if image_b64:
                    image_bytes = base64.b64decode(image_b64)
                    
            if image_bytes:
                try:
                    file_path = await save_cached_image(db, db_job.image_hash, image_bytes)
                except Exception:
                    logger.exception("Failed to save image from RunPod for job %s", db_job.runpod_job_id)
                    db_job.status = "FAILED"
                    db.commit()
                    return JobStatusResponse(status="FAILED", error="Enhanced image was not saved.")
                    
                db_job.status = "COMPLETED"
                db.commit()
                
                try:
                    img = Image.open(BytesIO(image_bytes))
                    width, height = img.size
                except Exception:
                    width, height = None, None
                
                filename = os.path.basename(file_path)
                image_url = f"{settings.PUBLIC_IMAGE_BASE_URL}/{filename}"
                logger.info(
                    "Saved file:\n%s\nReturned URL:\n%s\nExists:\n%s",
                    file_path,
                    image_url,
                    os.path.exists(file_path)
                )
                
                return JobStatusResponse(
                    status="COMPLETED",
                    image_url=image_url,
                    width=width,
                    height=height
                )
            else:
                db_job.status = "FAILED"
                db.commit()
                return JobStatusResponse(status="FAILED", error="RunPod returned COMPLETED but no image found in output")
                
        elif current_status in ["FAILED", "CANCELLED"]:
            logger.error(
                "RunPod job %s failed.\nFull response:\n%s",
                db_job.runpod_job_id,
                status_data
            )
            db_job.status = "FAILED"
            db.commit()
            
            return JobStatusResponse(
                status="FAILED",
                error=status_data.get("error", "RunPod job failed")
            )
            
        else:
            # QUEUED, IN_PROGRESS
            if current_status != db_job.status:
                db_job.status = current_status
                db.commit()
                
            return JobStatusResponse(status=current_status)
            
    except Exception as e:
        logger.exception("Error checking job %s: %s", db_job.runpod_job_id, e)
        # If check fails but DB status is known, we can just return it or throw an error.
        # It's better to just return the DB status for now if RunPod is temporarily unreachable.
        return JobStatusResponse(status=db_job.status)
