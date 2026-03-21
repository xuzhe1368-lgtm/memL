from __future__ import annotations

import asyncio
import httpx
from app.config import settings


class EmbeddingService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=settings.embed_timeout_sec)
        self._sem = asyncio.Semaphore(settings.embed_max_concurrency)

    async def close(self):
        await self._client.aclose()

    async def embed(self, text: str) -> list[float]:
        payload = {"model": settings.embed_model, "input": text}
        headers = {"Authorization": f"Bearer {settings.embed_api_key}"}
        last_err = None

        for i in range(settings.embed_max_retries + 1):
            try:
                async with self._sem:
                    r = await self._client.post(settings.embed_api_url, headers=headers, json=payload)
                    r.raise_for_status()
                    data = r.json()
                    return data["data"][0]["embedding"]
            except Exception as e:
                last_err = e
                if i < settings.embed_max_retries:
                    await asyncio.sleep(0.3 * (2 ** i))
                else:
                    raise last_err
