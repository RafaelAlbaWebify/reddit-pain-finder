from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from painfinder.analysis import detect_pain_signals
from painfinder.domain import PainCategory, SourceItem
from painfinder.opportunities import build_opportunity_clusters


class BenchmarkFormatError(RuntimeError):
    pass


@dataclass(frozen=True)
class BenchmarkCase:
    item: SourceItem
    expected_pain: bool
    expected_categories: tuple[PainCategory, ...]
    expected_cluster: str | None


@dataclass(frozen=True)
class BenchmarkResult:
    case_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    category_recall: float
    cluster_pair_precision: float
    cluster_pair_recall: float
    false_positive_ids: tuple[str, ...]
    false_negative_ids: tuple[str, ...]
    fragmentation_pairs: tuple[tuple[str, str], ...]
    overmerge_pairs: tuple[tuple[str, str], ...]


def load_benchmark(path: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise BenchmarkFormatError(
                f"Invalid JSON on line {line_number}: {error.msg}"
            ) from error
        if not isinstance(payload, dict):
            raise BenchmarkFormatError(
                f"Invalid benchmark case on line {line_number}: expected an object"
            )
        try:
            item_payload = payload["item"]
            expected_pain = payload["expected_pain"]
            if not isinstance(expected_pain, bool):
                raise TypeError("expected_pain must be boolean")
            item = SourceItem.model_validate(item_payload)
            categories = tuple(
                PainCategory(str(value))
                for value in _list(payload, "expected_categories")
            )
            expected_cluster = _optional_text(payload.get("expected_cluster"))
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise BenchmarkFormatError(
                f"Invalid benchmark case on line {line_number}: {error}"
            ) from error
        cases.append(
            BenchmarkCase(
                item=item,
                expected_pain=expected_pain,
                expected_categories=categories,
                expected_cluster=expected_cluster,
            )
        )
    return cases


def evaluate_benchmark(cases: list[BenchmarkCase]) -> BenchmarkResult:
    items = [case.item for case in cases]
    signals = detect_pain_signals(items)
    clusters = build_opportunity_clusters(items, signals)

    signals_by_id: dict[str, set[PainCategory]] = {}
    for signal in signals:
        signals_by_id.setdefault(signal.source_external_id, set()).add(signal.category)

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []
    expected_category_total = 0
    matched_category_total = 0

    for case in cases:
        predicted_categories = signals_by_id.get(case.item.external_id, set())
        predicted_pain = bool(predicted_categories)
        if case.expected_pain and predicted_pain:
            true_positive += 1
        elif case.expected_pain and not predicted_pain:
            false_negative += 1
            false_negative_ids.append(case.item.external_id)
        elif not case.expected_pain and predicted_pain:
            false_positive += 1
            false_positive_ids.append(case.item.external_id)
        else:
            true_negative += 1

        expected_category_total += len(case.expected_categories)
        matched_category_total += len(
            set(case.expected_categories) & predicted_categories
        )

    predicted_cluster_by_id = {
        source_id: cluster.key
        for cluster in clusters
        for source_id in cluster.source_ids
    }
    expected_cluster_by_id = {
        case.item.external_id: case.expected_cluster
        for case in cases
        if case.expected_cluster is not None
    }

    expected_pairs: set[tuple[str, str]] = set()
    predicted_pairs: set[tuple[str, str]] = set()
    eligible_ids = sorted(expected_cluster_by_id)
    for left, right in combinations(eligible_ids, 2):
        if expected_cluster_by_id[left] == expected_cluster_by_id[right]:
            expected_pairs.add((left, right))
        if (
            predicted_cluster_by_id.get(left) is not None
            and predicted_cluster_by_id.get(left) == predicted_cluster_by_id.get(right)
        ):
            predicted_pairs.add((left, right))

    matched_pairs = expected_pairs & predicted_pairs
    fragmentation = tuple(sorted(expected_pairs - predicted_pairs))
    overmerge = tuple(sorted(predicted_pairs - expected_pairs))

    return BenchmarkResult(
        case_count=len(cases),
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=_ratio(true_positive, true_positive + false_positive),
        recall=_ratio(true_positive, true_positive + false_negative),
        category_recall=_ratio(matched_category_total, expected_category_total),
        cluster_pair_precision=_ratio(len(matched_pairs), len(predicted_pairs)),
        cluster_pair_recall=_ratio(len(matched_pairs), len(expected_pairs)),
        false_positive_ids=tuple(sorted(false_positive_ids)),
        false_negative_ids=tuple(sorted(false_negative_ids)),
        fragmentation_pairs=fragmentation,
        overmerge_pairs=overmerge,
    )


def write_benchmark_results(
    result: BenchmarkResult,
    *,
    json_output: Path,
    html_output: Path,
) -> None:
    payload = {
        "case_count": result.case_count,
        "confusion_matrix": {
            "true_positive": result.true_positive,
            "false_positive": result.false_positive,
            "true_negative": result.true_negative,
            "false_negative": result.false_negative,
        },
        "metrics": {
            "precision": result.precision,
            "recall": result.recall,
            "category_recall": result.category_recall,
            "cluster_pair_precision": result.cluster_pair_precision,
            "cluster_pair_recall": result.cluster_pair_recall,
        },
        "false_positive_ids": result.false_positive_ids,
        "false_negative_ids": result.false_negative_ids,
        "fragmentation_pairs": result.fragmentation_pairs,
        "overmerge_pairs": result.overmerge_pairs,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(
        _html_report(result),
        encoding="utf-8",
    )


def _html_report(result: BenchmarkResult) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reddit Pain Finder — Benchmark Evaluation</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px; }}
section {{ border: 1px solid #d9dde5; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d9dde5; padding: 8px; text-align: left; }}
</style>
</head>
<body>
<h1>Benchmark Evaluation</h1>
<p>Reviewed cases: {result.case_count}</p>
<p>These metrics measure the current deterministic rules against this corpus only.</p>
<section>
<h2>Detection</h2>
<table>
<tr><th>Precision</th><td>{result.precision:.3f}</td></tr>
<tr><th>Recall</th><td>{result.recall:.3f}</td></tr>
<tr><th>Category recall</th><td>{result.category_recall:.3f}</td></tr>
<tr><th>False positives</th><td>{result.false_positive}</td></tr>
<tr><th>False negatives</th><td>{result.false_negative}</td></tr>
</table>
</section>
<section>
<h2>Clustering</h2>
<table>
<tr><th>Pair precision</th><td>{result.cluster_pair_precision:.3f}</td></tr>
<tr><th>Pair recall</th><td>{result.cluster_pair_recall:.3f}</td></tr>
<tr><th>Fragmented expected pairs</th><td>{len(result.fragmentation_pairs)}</td></tr>
<tr><th>Over-merged pairs</th><td>{len(result.overmerge_pairs)}</td></tr>
</table>
</section>
<p>Benchmark results do not estimate market size, demand, or willingness to pay.</p>
</body>
</html>"""


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
