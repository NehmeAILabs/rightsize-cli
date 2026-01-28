from __future__ import annotations

import csv
import json
import sys
from typing import Iterable

from rich.console import Console
from rich.table import Table
from rich.text import Text

from rightsize.models import BenchmarkResult


def render_results(
    results: list[BenchmarkResult],
    baseline_model: str | None,
    output_format: str,
) -> None:
    output_format = output_format.lower()
    if output_format == "json":
        _render_json(results)
    elif output_format == "csv":
        _render_csv(results)
    else:
        _render_table(results, baseline_model)


def _render_table(results: list[BenchmarkResult], baseline_model: str | None) -> None:
    console = Console()
    table = Table(title="Benchmark Results")
    table.add_column("Model")
    table.add_column("Accuracy", justify="right")
    table.add_column("Latency (p95)", justify="right")
    table.add_column("Cost/1k", justify="right")
    table.add_column("Savings", justify="right")

    baseline_cost = _baseline_cost(results, baseline_model)
    for r in sorted(results, key=lambda x: (x.cost_per_1k is None, x.cost_per_1k or 0.0)):
        savings_text = _format_savings(r, baseline_cost)
        table.add_row(
            r.model,
            f"{r.accuracy:.1%}",
            f"{r.latency_p95_ms:.0f}ms",
            _format_cost(r.cost_per_1k),
            savings_text,
        )
    console.print(table)


def _render_json(results: Iterable[BenchmarkResult]) -> None:
    payload = [r.model_dump() for r in results]
    sys.stdout.write(json.dumps(payload, indent=2))


def _render_csv(results: Iterable[BenchmarkResult]) -> None:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=[
            "model",
            "accuracy",
            "latency_p95_ms",
            "cost_per_1k",
            "total_runs",
            "successful_runs",
        ],
    )
    writer.writeheader()
    for r in results:
        writer.writerow(r.model_dump())


def _baseline_cost(results: list[BenchmarkResult], baseline_model: str | None) -> float | None:
    if baseline_model is None:
        return None
    for r in results:
        if r.model == baseline_model:
            return r.cost_per_1k
    return None


def _format_cost(cost: float | None) -> str:
    if cost is None:
        return "n/a"
    return f"${cost:.4f}"


def _format_savings(result: BenchmarkResult, baseline_cost: float | None) -> Text:
    if baseline_cost is None or result.cost_per_1k is None:
        return Text("—")
    if baseline_cost == 0:
        return Text("—")
    savings = (baseline_cost - result.cost_per_1k) / baseline_cost
    style = "green" if savings >= 0 else "red"
    return Text(f"{savings:+.1%}", style=style)
