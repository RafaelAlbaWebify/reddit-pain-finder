import json
from pathlib import Path
from typing import Annotated

import typer

from painfinder.analysis import detect_pain_signals
from painfinder.domain import ResearchRun
from painfinder.importers import ImportFormatError, deduplicate_items, import_source_items
from painfinder.opportunities import build_opportunity_clusters
from painfinder.opportunity_report import write_opportunity_report
from painfinder.playwright_collector import PlaywrightRedditCollector
from painfinder.reddit_fixture import extract_thread_fixture
from painfinder.report import write_html_report

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Reddit Pain Finder command line interface."""


@app.command()
def demo(
    input: Annotated[Path, typer.Option(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()],
) -> None:
    """Run the offline fixture-to-report vertical slice."""
    items = extract_thread_fixture(input)
    signals = detect_pain_signals(items)
    write_html_report(output, items, signals, source_kind="fixture")
    typer.echo(f"PASS: wrote {output} with {len(signals)} pain candidate(s)")


@app.command()
def discover(
    input: Annotated[Path, typer.Option(exists=True, readable=True)],
    output: Annotated[Path, typer.Option()] = Path("output/opportunities.html"),
) -> None:
    """Import evidence and generate a ranked opportunity report."""
    try:
        imported = import_source_items(input)
    except ImportFormatError as error:
        typer.echo(f"ERROR: {error}", err=True)
        raise typer.Exit(code=2) from error

    items = deduplicate_items(imported)
    signals = detect_pain_signals(items)
    clusters = build_opportunity_clusters(items, signals)
    write_opportunity_report(output, items=items, clusters=clusters)
    typer.echo(
        f"PASS: imported {len(imported)} item(s), retained {len(items)} unique item(s), "
        f"found {len(signals)} pain signal(s), built {len(clusters)} cluster(s)"
    )
    typer.echo(f"Report: {output}")


@app.command("live-smoke")
def live_smoke(
    subreddits: Annotated[str, typer.Option()],
    sort: Annotated[str, typer.Option()] = "new",
    max_threads: Annotated[int, typer.Option(min=1, max=10)] = 3,
    max_comments: Annotated[int, typer.Option(min=0, max=50)] = 10,
    artifacts_dir: Annotated[Path, typer.Option()] = Path("artifacts/live-smoke"),
) -> None:
    """Run a bounded headed-browser smoke collection."""
    seeds = [item.strip() for item in subreddits.split(",") if item.strip()]
    policy = ResearchRun(
        name="live-smoke",
        max_pages=max_threads + len(seeds) + 2,
        max_threads=max_threads,
        max_comments_per_thread=max_comments,
        max_runtime_seconds=900,
        live_access_enabled=True,
        concurrency=1,
    )
    result = PlaywrightRedditCollector(artifacts_dir=artifacts_dir).collect(
        policy=policy,
        subreddits=seeds,
        sort=sort,
    )

    signals = detect_pain_signals(result.items)
    stop_reason = result.stop_reason or "completed"
    report = artifacts_dir / "live-report.html"
    write_html_report(
        report,
        result.items,
        signals,
        source_kind="live",
        stop_reason=stop_reason,
    )

    summary = {
        "source_kind": "live",
        "subreddits": seeds,
        "sort": sort,
        "items_collected": len(result.items),
        "pain_candidates": len(signals),
        "stop_reason": stop_reason,
        "evidence": [
            evidence.model_dump(mode="json")
            for evidence in result.evidence
        ],
    }
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "collection-result.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    typer.echo(
        f"PASS: collected {len(result.items)} item(s), "
        f"found {len(signals)} pain candidate(s), "
        f"stop_reason={stop_reason}"
    )
    typer.echo(f"Report: {report}")


if __name__ == "__main__":
    app()
