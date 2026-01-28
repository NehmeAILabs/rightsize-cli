from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from typing import Callable

from rightsize.client import OpenRouterClient
from rightsize.judge import judge_output
from rightsize.models import BenchmarkResult, JudgeScore, ModelPricing, RunResult, TestCase
from rightsize.pricing import calculate_cost


async def run_benchmark(
    test_cases: list[TestCase],
    models: list[str],
    template: Callable[[str], str],
    client: OpenRouterClient,
    concurrency: int,
) -> list[RunResult]:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _run_single(semaphore, client, model, tc, idx, template)
        for model in models
        for idx, tc in enumerate(test_cases)
    ]
    return await asyncio.gather(*tasks)


async def _run_single(
    semaphore: asyncio.Semaphore,
    client: OpenRouterClient,
    model: str,
    test_case: TestCase,
    test_case_idx: int,
    template: Callable[[str], str],
) -> RunResult:
    async with semaphore:
        prompt = template(test_case.input_data)
        try:
            messages = [{"role": "user", "content": prompt}]
            output, input_tokens, output_tokens, latency_ms = await client.complete(
                model, messages, temperature=0.0
            )
            return RunResult(
                model=model,
                test_case_idx=test_case_idx,
                prompt=prompt,
                output=output,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            return RunResult(
                model=model,
                test_case_idx=test_case_idx,
                prompt=prompt,
                output="",
                latency_ms=0.0,
                input_tokens=0,
                output_tokens=0,
                success=False,
                error=str(exc),
            )


async def run_judging(
    run_results: list[RunResult],
    test_cases: list[TestCase],
    judge_model: str,
    client: OpenRouterClient,
    concurrency: int,
) -> dict[tuple[str, int], JudgeScore]:
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _judge_single(semaphore, client, judge_model, test_cases[r.test_case_idx], r)
        for r in run_results
        if r.success
    ]
    scores = await asyncio.gather(*tasks)
    return {(score[0], score[1]): score[2] for score in scores}


async def _judge_single(
    semaphore: asyncio.Semaphore,
    client: OpenRouterClient,
    judge_model: str,
    test_case: TestCase,
    result: RunResult,
) -> tuple[str, int, JudgeScore]:
    async with semaphore:
        score = await judge_output(
            client,
            judge_model,
            prompt=result.prompt,
            expected=test_case.expected_output,
            actual=result.output,
        )
        return result.model, result.test_case_idx, score


def aggregate_results(
    run_results: list[RunResult],
    judge_scores: dict[tuple[str, int], JudgeScore],
    pricing: dict[str, ModelPricing],
) -> list[BenchmarkResult]:
    by_model: dict[str, list[RunResult]] = defaultdict(list)
    for result in run_results:
        by_model[result.model].append(result)

    aggregated: list[BenchmarkResult] = []
    for model, results in by_model.items():
        successful = [r for r in results if r.success]
        latencies = sorted(r.latency_ms for r in successful if r.latency_ms > 0)
        latency_p95_ms = _p95(latencies)
        scores = [
            judge_scores[(r.model, r.test_case_idx)].score
            for r in successful
            if (r.model, r.test_case_idx) in judge_scores
        ]
        accuracy = sum(scores) / len(scores) if scores else 0.0

        costs = [
            calculate_cost(pricing, r.model, r.input_tokens, r.output_tokens)
            for r in successful
        ]
        if any(c is None for c in costs) or not costs:
            cost_per_1k = None
        else:
            avg_cost = sum(c for c in costs if c is not None) / len(costs)
            cost_per_1k = avg_cost * 1000

        aggregated.append(
            BenchmarkResult(
                model=model,
                accuracy=accuracy,
                latency_p95_ms=latency_p95_ms,
                cost_per_1k=cost_per_1k,
                total_runs=len(results),
                successful_runs=len(successful),
            )
        )
    return aggregated


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    idx = max(0, math.ceil(0.95 * len(values)) - 1)
    return values[idx]
