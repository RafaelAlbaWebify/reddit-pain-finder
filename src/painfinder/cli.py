from pathlib import Path
from typing import Annotated

import typer

from painfinder.analysis import detect_pain_signals
from painfinder.domain import ResearchRun
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
    write_html_report(output, items, signals)
    typer.echo(f"PASS: wrote {output} with {len(signals)} pain candidate(s)")


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
    result = PlaywrightRedditCollector(
        artifacts_dir=artifacts_dir
    ).collect(
        policy=policy,
        subreddits=seeds,
        sort=sort,
    )

    signals = detect_pain_signals(result.items)
    report = artifacts_dir / "live-report.html"
    write_html_report(report, result.items, signals)

    typer.echo(
        f"PASS: collected {len(result.items)} item(s), "
        f"found {len(signals)} pain candidate(s), "
        f"stop_reason={result.stop_reason or 'completed'}"
    )
    typer.echo(f"Report: {report}")


if __name__ == "__main__":
    app()
