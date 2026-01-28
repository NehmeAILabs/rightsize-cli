from __future__ import annotations

from pydantic import BaseModel


class TestCase(BaseModel):
    input_data: str
    expected_output: str | None = None


class ModelPricing(BaseModel):
    """Pricing per 1M tokens (from OpenRouter API)."""

    input: float
    output: float


class RunResult(BaseModel):
    model: str
    test_case_idx: int
    prompt: str  # The actual prompt sent to the model
    output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None = None


class JudgeScore(BaseModel):
    score: float
    reasoning: str


class BenchmarkResult(BaseModel):
    model: str
    accuracy: float
    latency_p95_ms: float
    cost_per_1k: float | None
    total_runs: int
    successful_runs: int
