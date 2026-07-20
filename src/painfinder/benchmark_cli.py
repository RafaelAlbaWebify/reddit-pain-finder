from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from painfinder.benchmark import (
    BenchmarkFormatError,
    evaluate_benchmark,
    load_benchmark,
    write_benchmark_results,
)

benchmark_app = typer.Typer(no_args_is_help=True)


@benchmark_app.command("run")
def run_benchmark(
    corpus: Annotated[Path, typer.Option(exists=True, readable=True)],
    json_output: Annotated[Path, typer.Option()] = Path(
        "output/benchmark-results.json"
    ),
    html_output: Annotated[Path, typer.Option()] = Path(
        "output/benchmark-results.html"
    ),
) -> None:
    """Evaluate detector and clustering rules against a reviewed corpus."""
    try:
        cases = load_benchmark(corpus)
    except BenchmarkFormatError as error:
        typer.echo(f"ERROR: {error}")
        raise typer.Exit(code=2) from error

    result = evaluate_benchmark(cases)
    write_benchmark_results(
        result,
        json_output=json_output,
        html_output=html_output,
    )
    typer.echo(
        f"PASS: evaluated {result.case_count} case(s); "
        f"precision={result.precision:.3f}, recall={result.recall:.3f}, "
        f"cluster_pair_recall={result.cluster_pair_recall:.3f}"
    )
    typer.echo(f"JSON: {json_output}")
    typer.echo(f"HTML: {html_output}")
