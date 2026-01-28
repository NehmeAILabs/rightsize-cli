from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from rightsize.models import ModelPricing

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


@dataclass
class OpenRouterClient:
    api_key: str
    timeout: float = 60.0
    _client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenRouterClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=OPENROUTER_BASE,
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, json_body: dict[str, Any] | None) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OpenRouterClient is not initialized. Use 'async with'.")

        backoff = 0.5
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                response = await self._client.request(method, path, json=json_body)
                if response.status_code >= 500 or response.status_code == 429:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                await asyncio.sleep(backoff)
                backoff *= 2
        if last_exc is None:
            raise RuntimeError("Request failed without exception.")
        raise last_exc

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> tuple[str, int, int, float]:
        start = time.perf_counter()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        data = await self._request("POST", "/chat/completions", payload)
        latency_ms = (time.perf_counter() - start) * 1000.0

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        return content, input_tokens, output_tokens, latency_ms

    async def fetch_models(self) -> dict[str, ModelPricing]:
        data = await self._request("GET", "/models", None)
        models: dict[str, ModelPricing] = {}
        for item in data.get("data", []):
            model_id = item.get("id")
            pricing = item.get("pricing") or {}
            prompt = pricing.get("prompt")
            completion = pricing.get("completion")
            if model_id and prompt is not None and completion is not None:
                try:
                    input_per_token = float(prompt)
                    output_per_token = float(completion)
                except (TypeError, ValueError):
                    continue
                models[model_id] = ModelPricing(
                    input=input_per_token * 1_000_000,
                    output=output_per_token * 1_000_000,
                )
        return models
