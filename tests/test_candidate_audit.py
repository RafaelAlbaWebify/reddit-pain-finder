from __future__ import annotations

from pathlib import Path

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.candidate_audit import (
    build_candidate_error_audit,
    write_candidate_error_audit,
)
from painfinder.domain import PainCategory, SourceItem, SourceType
from painfinder.pain_policy import FinalPolicyDecision


def _case(external_id: str, body: str, expected_pain: bool) -> BenchmarkCase:
    return BenchmarkCase(
        item=SourceItem(
            external_id=external_id,
            source_type=SourceType.POST,
            title="Title",
            body=body,
            subreddit="smallbusiness",
            canonical_url=f"https://reddit.com/{external_id}",
        ),
        expected_pain=expected_pain,
        expected_categories=(PainCategory.RELIABILITY,) if expected_pain else (),
        expected_cluster=None,
    )


def test_candidate_audit_contains_full_false_negative_and_false_positive() -> None:
    cases = [
        _case("miss", "An opaque approval process.", True),
        _case("false", "How do you organize your workday?", False),
        _case("correct", "We launched yesterday.", False),
    ]
    records = {
        "miss": CalibrationRecord(
            source_external_id="miss",
            expected_pain=True,
            candidate_count=0,
            duration_ms=1,
            decision=FinalPolicyDecision.REJECT,
        )
    }

    rows = build_candidate_error_audit(cases, records)

    assert [row.source_external_id for row in rows] == ["false", "miss"]
    assert rows[0].error_type == "false_positive"
    assert rows[0].detector_ids
    assert rows[1].error_type == "false_negative"
    assert rows[1].body == "An opaque approval process."
    assert rows[1].expected_categories == ("reliability",)
    assert rows[1].latest_decision == "reject"


def test_candidate_audit_writes_jsonl_and_markdown(tmp_path: Path) -> None:
    rows = build_candidate_error_audit(
        [_case("miss", "An opaque approval process.", True)],
        {},
    )
    jsonl = tmp_path / "audit.jsonl"
    markdown = tmp_path / "audit.md"

    write_candidate_error_audit(rows, jsonl_output=jsonl, markdown_output=markdown)

    assert '"source_external_id":"miss"' in jsonl.read_text(encoding="utf-8")
    assert "false_negative" in markdown.read_text(encoding="utf-8")
