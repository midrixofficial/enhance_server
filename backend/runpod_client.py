import httpx
import logging
import asyncio
from typing import Dict, Any
from .config import settings

logger = logging.getLogger(__name__)

class RunPodClient:
    def __init__(self):
        self.api_key = settings.RUNPOD_API_KEY
        self.endpoint_id = settings.RUNPOD_ENDPOINT_ID
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def submit_job(self, input_data: Dict[str, Any]) -> str:
        async with httpx.AsyncClient() as client:
            try:
                for attempt in range(3):
                    try:
                        logger.info(
                            "Submitting RunPod job. Image length=%d Output=%s",
                            len(input_data.get("image", "")),
                            input_data.get("output_format")
                        )
                        response = await client.post(
                            f"{self.base_url}/run",
                            headers=self.headers,
                            json={"input": input_data},
                            timeout=15.0
                        )
                        response.raise_for_status()
                        data = response.json()
                        logger.info("RunPod submit response: %s", data)
                        if "id" not in data:
                            raise ValueError(f"Missing 'id' in RunPod response: {data}")
                        return data.get("id")
                    except httpx.HTTPError as e:
                        logger.warning(f"RunPod submission attempt {attempt+1} failed: {e}")
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1)
            except Exception as e:
                logger.exception("RunPod submission failed: %s", e)
                raise

    async def check_job_status(self, job_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                for attempt in range(3):
                    try:
                        response = await client.get(
                            f"{self.base_url}/status/{job_id}",
                            headers=self.headers,
                            timeout=10.0
                        )
                        response.raise_for_status()
                        status = response.json()
                        logger.info("RunPod status response for %s: %s", job_id, status)
                        return status
                    except httpx.HTTPError as e:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1)
            except Exception as e:
                logger.exception("RunPod status check failed: %s", e)
                raise

runpod_client = RunPodClient()
