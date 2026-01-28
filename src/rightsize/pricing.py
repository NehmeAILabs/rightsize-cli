from __future__ import annotations

from rightsize.client import OpenRouterClient
from rightsize.models import ModelPricing


async def fetch_pricing(client: OpenRouterClient) -> dict[str, ModelPricing]:
    return await client.fetch_models()


def calculate_cost(
    pricing: dict[str, ModelPricing],
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    model_pricing = pricing.get(model)
    if model_pricing is None:
        return None
    return (input_tokens * model_pricing.input + output_tokens * model_pricing.output) / 1_000_000
