from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from painfinder.benchmark import BenchmarkFormatError, load_benchmark
from painfinder.benchmark_review import REVIEW_COLUMNS


class CalibrationError(RuntimeError):
    pass


EVIDENCE_COLUMNS = (
    "external_id",
    "source_type",
    "title",
    "body",
    "community",
    "canonical_url",
)
LABEL_COLUMNS = (
    "expected_pain",
    "expected_categories",
    "expected_cluster",
)


@dataclass(frozen=True)
class CorpusAudit:
    case_count: int
    positive_count: int
    negative_count: int
    communities: tuple[str, ...]
    categories: tuple[str, ...]
    multi_item_clusters: tuple[str, ...]
    duplicate_ids: tuple[str, ...]
    checks: dict[str, bool]

    @property
    def passed(self) -> bool:
        return all(self.checks.values())


def audit_corpus(path: Path) -> CorpusAudit:
    try:
        cases = load_benchmark(path)
    except BenchmarkFormatError as error:
        raise CalibrationError(str(error)) from error

    ids = [case.item.external_id for case in cases]
    duplicate_ids = tuple(sorted(item_id for item_id, count in Counter(ids).items() if count > 1))
    communities = tuple(sorted({case.item.subreddit for case in cases if case.item.subreddit}))
    categories = tuple(
        sorted({category.value for case in cases for category in case.expected_categories})
    )
    cluster_counts = Counter(
        case.expected_cluster for case in cases if case.expected_cluster is not None
    )
    multi_item_clusters = tuple(
        sorted(cluster for cluster, count in cluster_counts.items() if count >= 2)
    )
    positive_count = sum(case.expected_pain for case in cases)
    negative_count = len(cases) - positive_count
    checks = {
        "non_empty": bool(cases),
        "unique_external_ids": not duplicate_ids,
        "multiple_communities": len(communities) >= 2,
        "multiple_categories": len(categories) >= 2,
        "positive_examples": positive_count >= 1,
        "negative_examples": negative_count >= 1,
        "multiple_multi_item_clusters": len(multi_item_clusters) >= 2,
    }
    return CorpusAudit(
        case_count=len(cases),
        positive_count=positive_count,
        negative_count=negative_count,
        communities=communities,
        categories=categories,
        multi_item_clusters=multi_item_clusters,
        duplicate_ids=duplicate_ids,
        checks=checks,
    )


def write_corpus_audit(audit: CorpusAudit, output: Path) -> None:
    payload = {
        "passed": audit.passed,
        "case_count": audit.case_count,
        "positive_count": audit.positive_count,
        "negative_count": audit.negative_count,
        "communities": audit.communities,
        "categories": audit.categories,
        "multi_item_clusters": audit.multi_item_clusters,
        "duplicate_ids": audit.duplicate_ids,
        "checks": audit.checks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compare_review_worksheets(
    left: Path,
    right: Path,
    *,
    disagreements_output: Path,
    summary_output: Path,
) -> dict[str, object]:
    left_rows = _read_worksheet(left)
    right_rows = _read_worksheet(right)
    if set(left_rows) != set(right_rows):
        missing_left = sorted(set(right_rows) - set(left_rows))
        missing_right = sorted(set(left_rows) - set(right_rows))
        raise CalibrationError(
            "Reviewer worksheets contain different evidence IDs; "
            f"missing from left={missing_left}, "
            f"missing from right={missing_right}"
        )

    disagreements: list[dict[str, str]] = []
    evidence_mismatches: list[str] = []
    agreement_count = 0
    for external_id in sorted(left_rows):
        left_row = left_rows[external_id]
        right_row = right_rows[external_id]
        if any(left_row[column] != right_row[column] for column in EVIDENCE_COLUMNS):
            evidence_mismatches.append(external_id)
            continue
        differing_labels = [
            column for column in LABEL_COLUMNS if left_row[column] != right_row[column]
        ]
        if differing_labels:
            disagreements.append(
                _disagreement_row(
                    external_id,
                    left_row,
                    right_row,
                    differing_labels,
                )
            )
        else:
            agreement_count += 1

    if evidence_mismatches:
        raise CalibrationError(
            "Reviewer worksheets changed source evidence for IDs: " + ", ".join(evidence_mismatches)
        )

    _write_disagreements(disagreements_output, disagreements)
    item_count = len(left_rows)
    summary: dict[str, object] = {
        "item_count": item_count,
        "agreement_count": agreement_count,
        "disagreement_count": len(disagreements),
        "agreement_rate": (round(agreement_count / item_count, 4) if item_count else 0.0),
        "disagreement_ids": [row["external_id"] for row in disagreements],
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def compare_benchmark_results(
    before: Path,
    after: Path,
    output: Path,
) -> dict[str, object]:
    before_payload = _read_result(before)
    after_payload = _read_result(after)
    before_metrics = _mapping(before_payload, "metrics")
    after_metrics = _mapping(after_payload, "metrics")
    metric_names = (
        "precision",
        "recall",
        "category_recall",
        "cluster_pair_precision",
        "cluster_pair_recall",
    )
    metric_deltas = {
        name: round(
            float(after_metrics[name]) - float(before_metrics[name]),
            4,
        )
        for name in metric_names
    }
    error_fields = (
        "false_positive_ids",
        "false_negative_ids",
        "fragmentation_pairs",
        "overmerge_pairs",
    )
    error_count_deltas = {
        name: len(_list(after_payload, name)) - len(_list(before_payload, name))
        for name in error_fields
    }
    comparison: dict[str, object] = {
        "before_case_count": int(before_payload["case_count"]),
        "after_case_count": int(after_payload["case_count"]),
        "same_case_count": (before_payload["case_count"] == after_payload["case_count"]),
        "metric_deltas": metric_deltas,
        "error_count_deltas": error_count_deltas,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return comparison


def _disagreement_row(
    external_id: str,
    left: dict[str, str],
    right: dict[str, str],
    differing_labels: list[str],
) -> dict[str, str]:
    return {
        "external_id": external_id,
        "differing_fields": ",".join(differing_labels),
        "left_expected_pain": left["expected_pain"],
        "right_expected_pain": right["expected_pain"],
        "left_expected_categories": left["expected_categories"],
        "right_expected_categories": right["expected_categories"],
        "left_expected_cluster": left["expected_cluster"],
        "right_expected_cluster": right["expected_cluster"],
        "left_reviewer": left["reviewer"],
        "right_reviewer": right["reviewer"],
        "canonical_url": left["canonical_url"],
        "title": left["title"],
        "body": left["body"],
    }


def _write_disagreements(
    output: Path,
    disagreements: list[dict[str, str]],
) -> None:
    fields = (
        "external_id",
        "differing_fields",
        "left_expected_pain",
        "right_expected_pain",
        "left_expected_categories",
        "right_expected_categories",
        "left_expected_cluster",
        "right_expected_cluster",
        "left_reviewer",
        "right_reviewer",
        "canonical_url",
        "title",
        "body",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(disagreements)


def _read_worksheet(path: Path) -> dict[str, dict[str, str]]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        raise CalibrationError(f"Could not read worksheet: {error}") from error
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_COLUMNS:
            raise CalibrationError(
                "Invalid worksheet headers; expected: " + ", ".join(REVIEW_COLUMNS)
            )
        rows: dict[str, dict[str, str]] = {}
        for line_number, raw_row in enumerate(reader, start=2):
            row = {column: (raw_row.get(column) or "").strip() for column in REVIEW_COLUMNS}
            external_id = row["external_id"]
            if not external_id:
                raise CalibrationError(f"Blank external_id on line {line_number}")
            if external_id in rows:
                raise CalibrationError(f"Duplicate external_id in worksheet: {external_id}")
            rows[external_id] = row
    return rows


def _read_result(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CalibrationError(f"Could not read benchmark result: {error}") from error
    if not isinstance(payload, dict):
        raise CalibrationError("Benchmark result must be a JSON object")
    return payload


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise CalibrationError(f"Benchmark result field {key} must be an object")
    return value


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise CalibrationError(f"Benchmark result field {key} must be a list")
    return value
