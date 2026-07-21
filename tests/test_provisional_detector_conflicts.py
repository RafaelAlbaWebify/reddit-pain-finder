from __future__ import annotations

import csv
import json
from pathlib import Path

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.provisional_review import build_provisional_review


def _packet(path: Path, *, body: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "item-1",
                "source_type": "post",
                "title": "Workflow",
                "body": body,
                "community": "smallbusiness",
                "canonical_url": "https://example.com/item-1",
                "expected_pain": "",
                "expected_categories": "",
                "expected_cluster": "",
                "review_status": "unreviewed",
                "reviewer": "",
                "reviewed_at": "",
                "rationale": "",
            }
        )


def _review(path: Path, *, pain: bool, categories: list[str]) -> None:
    payload = {
        "external_id": "item-1",
        "expected_pain": pain,
        "expected_categories": categories,
        "expected_cluster": "manual-invoice" if pain else "",
        "confidence": 0.95,
        "rationale": "Independent blind review.",
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _run(tmp_path: Path, *, pain: bool, categories: list[str]) -> tuple[Path, Path, Path]:
    packet = tmp_path / "packet.csv"
    _packet(packet, body="We copy totals into a spreadsheet every week.")
    reviews = []
    for index in range(3):
        review = tmp_path / f"review-{index}.jsonl"
        _review(review, pain=pain, categories=categories)
        reviews.append(review)
    provisional = tmp_path / "provisional.csv"
    queue = tmp_path / "queue.csv"
    summary = tmp_path / "summary.json"
    build_provisional_review(
        packet,
        (reviews[0], reviews[1], reviews[2]),
        provisional_output=provisional,
        approval_queue_output=queue,
        summary_output=summary,
        audit_percent=0,
    )
    return provisional, queue, summary


def test_detector_conflict_is_escalated(tmp_path: Path) -> None:
    provisional, queue, summary = _run(tmp_path, pain=False, categories=[])
    with provisional.open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle)) == []
    with queue.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["escalation_reasons"] == "detector_conflict"
    assert rows[0]["detector_pain"] == "true"
    assert rows[0]["detector_categories"] == "manual_work"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["detector_conflict_count"] == 1


def test_matching_detector_and_consensus_remains_provisional(tmp_path: Path) -> None:
    provisional, queue, summary = _run(
        tmp_path,
        pain=True,
        categories=["manual_work"],
    )
    with provisional.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["detector_pain"] == "true"
    assert rows[0]["detector_categories"] == "manual_work"
    with queue.open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle)) == []
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["detector_conflict_count"] == 0
