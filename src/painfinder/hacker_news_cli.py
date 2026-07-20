from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from painfinder.analysis import detect_pain_signals
from painfinder.domain import ResearchRun
from painfinder.hacker_news import ALLOWED_FEEDS, HackerNewsCollector
from painfinder.opportunities import build_opportunity_clusters
from painfinder.opportunity_report import write_opportunity_report

hacker_news_app = typer.Typer(no_args_is_help=True)


@hacker_news_app.command("smoke")
def smoke(
    feed: Annotated[str, typer.Option()] = "askstories",
    max_threads: Annotated[int, typer.Option(min=1, max=10)] = 3,
    max_comments: Annotated[int, typer.Option(min=0, max=20)] = 5,
    artifacts_dir: Annotated[Path, typer.Option()] = Path("artifacts/hacker-news"),
) -> None:
    """Run a bounded read-only Hacker News API collection."""
    if feed not in ALLOWED_FEEDS:
        typer.echo(
            "ERROR: unsupported feed; choose one of "
            + ", ".join(sorted(ALLOWED_FEEDS))
        )
        raise typer.Exit(code=2)

    policy = ResearchRun(
        name="hacker-news-smoke",
        max_pages=1 + max_threads * (1 + max_comments),
        max_threads=max_threads,
        max_comments_per_thread=max_comments,
        max_runtime_seconds=900,
        min_delay_seconds=1.0,
        live_access_enabled=True,
        concurrency=1,
    )
    result = HackerNewsCollector().collect(policy=policy, feed=feed)
    signals = detect_pain_signals(result.items)
    clusters = build_opportunity_clusters(result.items, signals)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report = artifacts_dir / "opportunities.html"
    summary = artifacts_dir / "collection-result.json"
    evidence_jsonl = artifacts_dir / "source-items.jsonl"

    write_opportunity_report(report, items=result.items, clusters=clusters)
    summary.write_text(
        json.dumps(
            {
                "source": "hacker_news",
                "feed": feed,
                "items_collected": len(result.items),
                "pain_signals": len(signals),
                "clusters": len(clusters),
                "stop_reason": result.stop_reason or "completed",
                "evidence": [
                    {
                        "url": evidence.url,
                        "status": evidence.status,
                        "detail": evidence.detail,
                    }
                    for evidence in result.evidence
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    evidence_jsonl.write_text(
        "\n".join(
            json.dumps(item.model_dump(mode="json"))
            for item in result.items
        )
        + ("\n" if result.items else ""),
        encoding="utf-8",
    )

    typer.echo(
        f"PASS: collected {len(result.items)} item(s), "
        f"found {len(signals)} pain signal(s), "
        f"built {len(clusters)} cluster(s), "
        f"stop_reason={result.stop_reason or 'completed'}"
    )
    typer.echo(f"Report: {report}")
    typer.echo(f"Summary: {summary}")
    typer.echo(f"Evidence: {evidence_jsonl}")
