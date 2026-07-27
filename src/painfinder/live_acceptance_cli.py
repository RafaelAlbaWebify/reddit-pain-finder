from __future__ import annotations

import argparse
from pathlib import Path

from painfinder.analysis import detect_pain_signals
from painfinder.domain import ResearchRun
from painfinder.live_acceptance import (
    evaluate_live_acceptance,
    write_live_acceptance_summary,
)
from painfinder.opportunities import build_opportunity_clusters
from painfinder.opportunity_report import write_opportunity_report
from painfinder.playwright_collector import PlaywrightRedditCollector


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded live Reddit collection and operational acceptance check."
        ),
    )
    parser.add_argument("--subreddits", required=True)
    parser.add_argument("--sort", choices=("new", "hot", "rising"), default="new")
    parser.add_argument("--max-threads", type=int, default=3)
    parser.add_argument("--max-comments", type=int, default=8)
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts/live-acceptance"),
    )
    arguments = parser.parse_args()

    seeds = [
        value.strip()
        for value in arguments.subreddits.split(",")
        if value.strip()
    ]
    if not seeds:
        print("ERROR: at least one subreddit is required")
        return 2

    artifacts = arguments.artifacts_dir
    report_path = artifacts / "opportunities.html"
    items_path = artifacts / "source-items.jsonl"
    summary_path = artifacts / "acceptance-summary.json"
    policy = ResearchRun(
        name="live-acceptance",
        max_pages=arguments.max_threads + len(seeds) + 2,
        max_threads=arguments.max_threads,
        max_comments_per_thread=arguments.max_comments,
        max_runtime_seconds=900,
        live_access_enabled=True,
        concurrency=1,
        min_delay_seconds=2.0,
    )

    collection = PlaywrightRedditCollector(artifacts_dir=artifacts).collect(
        policy=policy,
        subreddits=seeds,
        sort=arguments.sort,
    )
    signals = detect_pain_signals(collection.items)
    clusters = build_opportunity_clusters(collection.items, signals)
    artifacts.mkdir(parents=True, exist_ok=True)
    items_path.write_text(
        "".join(item.model_dump_json() + "\n" for item in collection.items),
        encoding="utf-8",
    )
    write_opportunity_report(report_path, items=collection.items, clusters=clusters)
    summary = evaluate_live_acceptance(
        stop_reason=collection.stop_reason,
        items=collection.items,
        pain_signals=len(signals),
        opportunity_clusters=len(clusters),
        report_path=report_path,
        items_path=items_path,
        evidence=collection.evidence,
    )
    write_live_acceptance_summary(summary, summary_path)

    status = "PASS" if summary.passed else "FAIL"
    print(
        f"{status}: items={summary.items_collected}, signals={summary.pain_signals}, "
        f"clusters={summary.opportunity_clusters}, stop_reason={summary.stop_reason}"
    )
    if summary.obstruction is not None:
        print(f"Obstruction: {summary.obstruction}")
    print(f"Summary: {summary_path}")
    print(f"Report: {report_path}")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
