from __future__ import annotations

import asyncio
import csv
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from rightsize.client import OpenRouterClient
from rightsize.config import Settings
from rightsize.models import ModelPricing, TestCase
from rightsize.output import render_results
from rightsize.pricing import fetch_pricing
from rightsize.runner import aggregate_results, run_benchmark, run_judging
from rightsize.template import load_template

app = typer.Typer(no_args_is_help=True)


@app.command()
def benchmark(
    csv_file: Path = typer.Argument(..., help="CSV with input_data and expected_output columns"),
    template: Path = typer.Option(..., "--template", "-t", help="Prompt template file"),
    models: list[str] = typer.Option(..., "--model", "-m", help="Model IDs to test"),
    judge_model: str = typer.Option(..., "--judge", "-j", help="Model for judging outputs"),
    baseline: str | None = typer.Option(None, "--baseline", "-b", help="Baseline model for savings calc"),
    concurrency: int = typer.Option(10, "--concurrency", "-c"),
    output_format: str = typer.Option("table", "--output", "-o", help="table|json|csv"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed outputs and scores"),
) -> None:
    """Benchmark prompts against multiple LLMs via OpenRouter."""
    console = Console()
    settings = Settings()
    test_cases = _load_test_cases(csv_file)
    renderer = load_template(template)

    if not models:
        raise typer.BadParameter("At least one --model is required.")
    if output_format.lower() not in {"table", "json", "csv"}:
        raise typer.BadParameter("Output must be one of: table, json, csv.")

    # Dedupe models and auto-add baseline if specified
    seen = set()
    unique_models = []
    for m in models:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)
    if baseline and baseline not in seen:
        console.print(f"[dim]Adding baseline '{baseline}' to model list[/dim]")
        unique_models.append(baseline)
    models = unique_models

    has_expected = all(tc.expected_output is not None for tc in test_cases)
    if has_expected:
        console.print(f"[dim]Using expected outputs from CSV for judging[/dim]")
    else:
        console.print(f"[dim]No expected outputs - judge will score on general quality[/dim]")

    async def _run() -> None:
        async with OpenRouterClient(
            api_key=settings.openrouter_api_key,
            timeout=settings.timeout_seconds,
        ) as client:
            pricing = await fetch_pricing(client)

            console.print(f"[dim]Running benchmark on {len(models)} model(s) x {len(test_cases)} test case(s)...[/dim]")
            run_results = await run_benchmark(
                test_cases=test_cases,
                models=models,
                template=renderer,
                client=client,
                concurrency=concurrency,
            )

            if verbose:
                console.print("\n[bold]Model Outputs:[/bold]")
                for r in run_results:
                    tc = test_cases[r.test_case_idx]
                    console.print(f"[cyan]{r.model}[/cyan] | TC {r.test_case_idx}")
                    console.print(f"  Expected: [green]{tc.expected_output}[/green]")
                    console.print(f"  Actual:   [yellow]{r.output!r}[/yellow]")
                    console.print()

            console.print(f"[dim]Judging outputs using {judge_model}...[/dim]")
            judge_scores = await run_judging(
                run_results=run_results,
                test_cases=test_cases,
                judge_model=judge_model,
                client=client,
                concurrency=concurrency,
            )

            if verbose:
                console.print("\n[bold]Judge Scores:[/bold]")
                for (model, tc_idx), score in judge_scores.items():
                    console.print(f"[cyan]{model}[/cyan] | TC {tc_idx}: [{'green' if score.score >= 0.8 else 'red'}]{score.score:.1%}[/] - {score.reasoning}")
                console.print()

            aggregated = aggregate_results(run_results, judge_scores, pricing)
            render_results(aggregated, baseline, output_format)

    asyncio.run(_run())


@app.command()
def models() -> None:
    settings = Settings()

    async def _run() -> None:
        async with OpenRouterClient(
            api_key=settings.openrouter_api_key,
            timeout=settings.timeout_seconds,
        ) as client:
            pricing = await fetch_pricing(client)
        _render_models(pricing)

    asyncio.run(_run())


def _load_test_cases(path: Path) -> list[TestCase]:
    if not path.exists():
        raise typer.BadParameter(f"CSV file not found: {path}")
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if "input_data" not in (reader.fieldnames or []):
            raise typer.BadParameter("CSV must include an input_data column.")
        test_cases = []
        for row in reader:
            test_cases.append(
                TestCase(
                    input_data=row.get("input_data", ""),
                    expected_output=row.get("expected_output") or None,
                )
            )
        if not test_cases:
            raise typer.BadParameter("CSV must contain at least one row.")
        return test_cases


def _render_models(pricing: dict[str, ModelPricing]) -> None:
    console = Console()
    table = Table(title="OpenRouter Models (Pricing)")
    table.add_column("Model")
    table.add_column("Input $/1M", justify="right")
    table.add_column("Output $/1M", justify="right")

    for model_id in sorted(pricing.keys()):
        model_pricing = pricing[model_id]
        table.add_row(model_id, f"{model_pricing.input:.6f}", f"{model_pricing.output:.6f}")
    console.print(table)
