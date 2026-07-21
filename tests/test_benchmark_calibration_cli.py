from __future__ import annotations

import csv
import json
from pathlib import Path

from typer.testing import CliRunner

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.cli import app


def _case(
    external_id: str,
    *,
    community: str,
    pain: bool,
    categories: list[str],
    cluster: str | None,
) -> dict[str, object]:
    return {
        "item": {
            "external_id": external_id,
            "source_type": "post",
            "title": f"Title {external_id}",
            "body": f"Body {external_id}",
            "subreddit": community,
            "canonical_url": f"https://example.com/{external_id}",
        },
        "expected_pain": pain,
        "expected_categories": categories,
        "expected_cluster": cluster,
    }


def _write_jsonl(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(case) for case in cases) + "\n",
        encoding="utf-8",
    )


def _review_row(
    external_id: str,
    *,
    reviewer: str,
    pain: str,
    categories: str,
    cluster: str,
) -> dict[str, str]:
    return {
        "external_id": external_id,
        "source_type": "post",
        "title": f"Title {external_id}",
        "body": f"Body {external_id}",
        "community": "smallbusiness",
        "canonical_url": f"https://example.com/{external_id}",
        "expected_pain": pain,
        "expected_categories": categories,
        "expected_cluster": cluster,
        "review_status": "resolved",
        "reviewer": reviewer,
        "reviewed_at": "2026-07-20T12:00:00+00:00",
        "rationale": "Independent review",
    }


def _write_worksheet(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_audit_corpus_passes_representative_prerequisites(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    _write_jsonl(
        corpus,
        [
            _case("a", community="one", pain=True, categories=["manual_work"], cluster="x"),
            _case("b", community="two", pain=True, categories=["manual_work"], cluster="x"),
            _case("c", community="one", pain=True, categories=["reliability"], cluster="y"),
            _case("d", community="two", pain=True, categories=["reliability"], cluster="y"),
            _case("e", community="two", pain=False, categories=[], cluster=None),
        ],
    )
    output = tmp_path / "audit.json"
    result = CliRunner().invoke(
        app,
        ["benchmark", "audit-corpus", "--corpus", str(corpus), "--json-output", str(output)],
    )
    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["checks"]["multiple_multi_item_clusters"] is True


def test_audit_corpus_reports_failed_prerequisites(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    _write_jsonl(
        corpus,
        [_case("a", community="one", pain=True, categories=["manual_work"], cluster="x")],
    )
    output = tmp_path / "audit.json"
    result = CliRunner().invoke(
        app,
        ["benchmark", "audit-corpus", "--corpus", str(corpus), "--json-output", str(output)],
    )
    assert result.exit_code == 2
    assert "corpus audit failed" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["checks"]["negative_examples"] is False


def test_compare_reviews_extracts_disagreement_queue(tmp_path: Path) -> None:
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    _write_worksheet(
        left,
        [
            _review_row(
                "a",
                reviewer="reviewer-a",
                pain="true",
                categories="manual_work",
                cluster="x",
            ),
            _review_row("b", reviewer="reviewer-a", pain="false", categories="", cluster=""),
        ],
    )
    _write_worksheet(
        right,
        [
            _review_row(
                "a",
                reviewer="reviewer-b",
                pain="true",
                categories="reliability",
                cluster="x",
            ),
            _review_row("b", reviewer="reviewer-b", pain="false", categories="", cluster=""),
        ],
    )
    disagreements = tmp_path / "disagreements.csv"
    summary = tmp_path / "summary.json"
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "compare-reviews",
            "--left",
            str(left),
            "--right",
            str(right),
            "--disagreements-output",
            str(disagreements),
            "--json-output",
            str(summary),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["agreement_count"] == 1
    assert payload["disagreement_ids"] == ["a"]
    with disagreements.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["differing_fields"] == "expected_categories"


def test_compare_reviews_rejects_changed_evidence(tmp_path: Path) -> None:
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    left_row = _review_row(
        "a",
        reviewer="reviewer-a",
        pain="true",
        categories="manual_work",
        cluster="x",
    )
    right_row = _review_row(
        "a",
        reviewer="reviewer-b",
        pain="true",
        categories="manual_work",
        cluster="x",
    )
    right_row["body"] = "Changed source evidence"
    _write_worksheet(left, [left_row])
    _write_worksheet(right, [right_row])
    result = CliRunner().invoke(
        app,
        ["benchmark", "compare-reviews", "--left", str(left), "--right", str(right)],
    )
    assert result.exit_code == 2
    assert "changed source evidence" in result.stdout


def test_compare_results_records_metric_and_error_deltas(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    base = {
        "case_count": 4,
        "metrics": {
            "precision": 0.5,
            "recall": 0.5,
            "category_recall": 0.25,
            "cluster_pair_precision": 0.5,
            "cluster_pair_recall": 0.5,
        },
        "false_positive_ids": ["a"],
        "false_negative_ids": ["b"],
        "fragmentation_pairs": [["a", "b"]],
        "overmerge_pairs": [],
    }
    improved = {
        **base,
        "metrics": {
            **base["metrics"],
            "precision": 0.75,
            "recall": 1.0,
        },
        "false_positive_ids": [],
        "false_negative_ids": [],
    }
    before.write_text(json.dumps(base), encoding="utf-8")
    after.write_text(json.dumps(improved), encoding="utf-8")
    output = tmp_path / "comparison.json"
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "compare-results",
            "--before",
            str(before),
            "--after",
            str(after),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["metric_deltas"]["precision"] == 0.25
    assert payload["error_count_deltas"]["false_negative_ids"] == -1
