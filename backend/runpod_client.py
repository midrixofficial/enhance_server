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
                        response = await client.post(
                            f"{self.base_url}/run",
                            headers=self.headers,
                            json={"input": input_data},
                            timeout=15.0
                        )
                        response.raise_for_status()
                        data = response.json()
                        return data.get("id")
                    except httpx.HTTPError as e:
                        logger.warning(f"RunPod submission attempt {attempt+1} failed: {e}")
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"RunPod submission failed: {e}")
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
                        return response.json()
                    except httpx.HTTPError as e:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"RunPod status check failed: {e}")
                raise

runpod_client = RunPodClient()
