from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.cli import app


def _packet(path: Path, ids: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for external_id in ids:
            writer.writerow(
                {
                    "external_id": external_id,
                    "source_type": "post",
                    "title": f"Invoice workflow {external_id}",
                    "body": "We manually update this spreadsheet every week.",
                    "community": "smallbusiness",
                    "canonical_url": f"https://example.com/{external_id}",
                    "expected_pain": "",
                    "expected_categories": "",
                    "expected_cluster": "",
                    "review_status": "unreviewed",
                    "reviewer": "",
                    "reviewed_at": "",
                    "rationale": "",
                }
            )


def _decision(
    external_id: str,
    *,
    pain: bool = True,
    confidence: float = 0.95,
    cluster: str = "invoice-work",
) -> dict[str, object]:
    return {
        "external_id": external_id,
        "expected_pain": pain,
        "expected_categories": ["manual_work"] if pain else [],
        "expected_cluster": cluster if pain else "",
        "confidence": confidence,
        "rationale": "Evidence supports this decision.",
    }


def _reviews(path: Path, decisions: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(decision) for decision in decisions) + "\n",
        encoding="utf-8",
    )


def _invoke(
    tmp_path: Path,
    packet: Path,
    reviewers: list[Path],
    *,
    audit_percent: int = 0,
) -> tuple[object, Path, Path, Path]:
    provisional = tmp_path / "provisional.csv"
    queue = tmp_path / "queue.csv"
    summary = tmp_path / "summary.json"
    arguments = [
        "benchmark",
        "build-provisional-review",
        "--blind-packet",
        str(packet),
    ]
    for reviewer in reviewers:
        arguments.extend(["--reviewer-output", str(reviewer)])
    arguments.extend(
        [
            "--provisional-output",
            str(provisional),
            "--approval-queue-output",
            str(queue),
            "--summary-output",
            str(summary),
            "--audit-percent",
            str(audit_percent),
        ]
    )
    result = CliRunner().invoke(app, arguments)
    return result, provisional, queue, summary


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_unanimous_high_confidence_is_provisional(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    _packet(packet, ["one"])
    reviewers = [tmp_path / f"reviewer-{index}.jsonl" for index in range(3)]
    for reviewer in reviewers:
        _reviews(reviewer, [_decision("one")])

    result, provisional, queue, summary = _invoke(tmp_path, packet, reviewers)

    assert result.exit_code == 0
    assert len(_rows(provisional)) == 1
    assert _rows(queue) == []
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["unanimous_count"] == 1
    assert payload["provisional_count"] == 1


def test_majority_disagreement_goes_to_human_queue(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    _packet(packet, ["one"])
    reviewers = [tmp_path / f"reviewer-{index}.jsonl" for index in range(3)]
    _reviews(reviewers[0], [_decision("one")])
    _reviews(reviewers[1], [_decision("one")])
    _reviews(reviewers[2], [_decision("one", pain=False)])

    result, provisional, queue, _ = _invoke(tmp_path, packet, reviewers)

    assert result.exit_code == 0
    assert _rows(provisional) == []
    queue_rows = _rows(queue)
    assert len(queue_rows) == 1
    assert queue_rows[0]["agreement"] == "majority"
    assert "reviewer_disagreement" in queue_rows[0]["escalation_reasons"]


def test_low_confidence_and_audit_sample_are_escalated(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    _packet(packet, ["one"])
    reviewers = [tmp_path / f"reviewer-{index}.jsonl" for index in range(3)]
    for reviewer in reviewers:
        _reviews(reviewer, [_decision("one", confidence=0.6)])

    result, provisional, queue, _ = _invoke(
        tmp_path,
        packet,
        reviewers,
        audit_percent=100,
    )

    assert result.exit_code == 0
    assert _rows(provisional) == []
    reasons = _rows(queue)[0]["escalation_reasons"]
    assert "low_confidence" in reasons
    assert "audit_sample" in reasons


def test_mismatched_reviewer_ids_fail_without_outputs(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    _packet(packet, ["one"])
    reviewers = [tmp_path / f"reviewer-{index}.jsonl" for index in range(3)]
    _reviews(reviewers[0], [_decision("one")])
    _reviews(reviewers[1], [_decision("one")])
    _reviews(reviewers[2], [_decision("other")])

    result, provisional, queue, summary = _invoke(tmp_path, packet, reviewers)

    assert result.exit_code == 2
    assert "evidence IDs differ" in result.stdout
    assert not provisional.exists()
    assert not queue.exists()
    assert not summary.exists()


def test_exactly_three_reviewer_outputs_are_required(tmp_path: Path) -> None:
    packet = tmp_path / "packet.csv"
    _packet(packet, ["one"])
    reviewer = tmp_path / "reviewer.jsonl"
    _reviews(reviewer, [_decision("one")])

    result, _, _, _ = _invoke(tmp_path, packet, [reviewer])

    assert result.exit_code == 2
    assert "exactly three" in result.stdout
