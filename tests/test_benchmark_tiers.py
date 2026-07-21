from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.benchmark_tiers import TieredBenchmarkError, write_tiered_benchmark_report


def _inputs(tmp_path: Path, label: str) -> tuple[Path, Path]:
    provisional = tmp_path / "provisional.csv"
    with provisional.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "p1",
                "source_type": "post",
                "title": "Neutral update",
                "body": "The weekly meeting starts at ten.",
                "community": "general",
                "canonical_url": "https://example.com/p1",
                "expected_pain": label,
                "expected_categories": "",
                "expected_cluster": "",
                "review_status": "provisional",
                "reviewer": "ai_consensus",
                "reviewed_at": "",
                "rationale": "No workflow problem stated.",
            }
        )
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        json.dumps(
            {
                "item": {
                    "external_id": "g1",
                    "source_type": "post",
                    "title": "Neutral notice",
                    "body": "The office opens at nine.",
                    "subreddit": "general",
                    "canonical_url": "https://example.com/g1",
                },
                "expected_pain": False,
                "expected_categories": [],
                "expected_cluster": None,
            }
        ) + "\n",
        encoding="utf-8",
    )
    return provisional, gold


def test_writes_separate_tiers(tmp_path: Path) -> None:
    provisional, gold = _inputs(tmp_path, "false")
    json_output = tmp_path / "report.json"
    html_output = tmp_path / "report.html"
    payload = write_tiered_benchmark_report(
        provisional,
        gold,
        json_output=json_output,
        html_output=html_output,
    )
    assert payload["provisional"]["provenance"] == "ai_unanimous_not_human_approved"
    assert payload["gold"]["provenance"] == "explicitly_human_approved"
    assert json_output.exists()
    assert html_output.exists()


def test_invalid_label_writes_nothing(tmp_path: Path) -> None:
    provisional, gold = _inputs(tmp_path, "unknown")
    json_output = tmp_path / "report.json"
    html_output = tmp_path / "report.html"
    with pytest.raises(TieredBenchmarkError):
        write_tiered_benchmark_report(
            provisional,
            gold,
            json_output=json_output,
            html_output=html_output,
        )
    assert not json_output.exists()
    assert not html_output.exists()
