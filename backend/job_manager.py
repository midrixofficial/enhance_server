import asyncio
import logging
import base64
from sqlalchemy.orm import Session
from .runpod_client import runpod_client
from .models import Job
from .database import SessionLocal
from .image_cache import save_cached_image

logger = logging.getLogger(__name__)

class JobManager:
    async def poll_job(self, internal_job_id: str, runpod_job_id: str, image_hash: str):
        max_retries = 150 # Poll for 5 minutes maximum
        
        for _ in range(max_retries):
            try:
                status_data = await runpod_client.check_job_status(runpod_job_id)
                status = status_data.get("status")
                
                if status == "COMPLETED":
                    logger.info(f"Job {runpod_job_id} completed. Caching result.")
                    output = status_data.get("output", {})
                    
                    image_bytes = None
                    if isinstance(output, str):
                        image_bytes = base64.b64decode(output)
                    elif isinstance(output, dict):
                        image_b64 = output.get("image_b64") or output.get("image")
                        if image_b64:
                            image_bytes = base64.b64decode(image_b64)
                        
                    if image_bytes:
                        db = SessionLocal()
                        try:
                            await save_cached_image(db, image_hash, image_bytes)
                            db_job = db.query(Job).filter(Job.job_id == internal_job_id).first()
                            if db_job:
                                db_job.status = "COMPLETED"
                                db.commit()
                        finally:
                            db.close()
                    break
                    
                elif status in ["FAILED", "CANCELLED"]:
                    logger.error(
                        "RunPod job %s failed.\nFull response:\n%s",
                        runpod_job_id,
                        status_data
                    )
                    db = SessionLocal()
                    try:
                        db_job = db.query(Job).filter(Job.job_id == internal_job_id).first()
                        if db_job:
                            db_job.status = "FAILED"
                            db.commit()
                    finally:
                        db.close()
                    break
                    
            except Exception as e:
                logger.exception("Error polling job %s: %s", runpod_job_id, e)
            
            await asyncio.sleep(2)
        else:
            logger.error(f"Job {runpod_job_id} polling timeout")
            db = SessionLocal()
            try:
                db_job = db.query(Job).filter(Job.job_id == internal_job_id).first()
                if db_job:
                    db_job.status = "FAILED"
                    db.commit()
            finally:
                db.close()

job_manager = JobManager()
