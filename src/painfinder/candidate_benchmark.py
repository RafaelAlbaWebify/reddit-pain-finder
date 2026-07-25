from __future__ import annotations

import html
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from painfinder.benchmark import BenchmarkCase
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import CandidateSignal, EvidenceField


@dataclass(frozen=True)
class CandidateBenchmarkResult:
    case_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    average_signals_per_item: float
    evidence_span_validity: float
    signal_type_counts: dict[str, int]
    false_positive_ids: tuple[str, ...]
    false_negative_ids: tuple[str, ...]


def evaluate_candidate_benchmark(
    cases: list[BenchmarkCase],
) -> CandidateBenchmarkResult:
    items = [case.item for case in cases]
    signals = generate_candidate_signals(items)

    signals_by_id: dict[str, list[CandidateSignal]] = {}
    for signal in signals:
        signals_by_id.setdefault(signal.source_external_id, []).append(signal)

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []

    for case in cases:
        predicted = bool(signals_by_id.get(case.item.external_id))
        if case.expected_pain and predicted:
            true_positive += 1
        elif case.expected_pain and not predicted:
            false_negative += 1
            false_negative_ids.append(case.item.external_id)
        elif not case.expected_pain and predicted:
            false_positive += 1
            false_positive_ids.append(case.item.external_id)
        else:
            true_negative += 1

    valid_spans = 0
    total_spans = 0
    items_by_id = {case.item.external_id: case.item for case in cases}
    for signal in signals:
        item = items_by_id[signal.source_external_id]
        for span in signal.evidence_spans:
            total_spans += 1
            source = item.title if span.field is EvidenceField.TITLE else item.body
            if source[span.start : span.end] == span.text:
                valid_spans += 1

    signal_type_counts = Counter(signal.signal_type.value for signal in signals)

    return CandidateBenchmarkResult(
        case_count=len(cases),
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=_ratio(true_positive, true_positive + false_positive),
        recall=_ratio(true_positive, true_positive + false_negative),
        average_signals_per_item=_ratio(len(signals), len(cases)),
        evidence_span_validity=_ratio(valid_spans, total_spans),
        signal_type_counts=dict(sorted(signal_type_counts.items())),
        false_positive_ids=tuple(sorted(false_positive_ids)),
        false_negative_ids=tuple(sorted(false_negative_ids)),
    )


def write_candidate_benchmark_results(
    result: CandidateBenchmarkResult,
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
            "average_signals_per_item": result.average_signals_per_item,
            "evidence_span_validity": result.evidence_span_validity,
        },
        "signal_type_counts": result.signal_type_counts,
        "false_positive_ids": result.false_positive_ids,
        "false_negative_ids": result.false_negative_ids,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(_html_report(result), encoding="utf-8")


def _html_report(result: CandidateBenchmarkResult) -> str:
    rows = "\n".join(
        f"<tr><td>{html.escape(signal_type)}</td><td>{count}</td></tr>"
        for signal_type, count in result.signal_type_counts.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reddit Pain Finder — Candidate Benchmark</title>
<style>
body {{
  font-family: system-ui, sans-serif;
  max-width: 1000px;
  margin: 40px auto;
  padding: 0 20px;
}}
section {{ border: 1px solid #d9dde5; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d9dde5; padding: 8px; text-align: left; }}
</style>
</head>
<body>
<h1>Candidate Generation Benchmark</h1>
<p>Reviewed cases: {result.case_count}</p>
<section>
<h2>Candidate detection</h2>
<table>
<tr><th>Precision</th><td>{result.precision:.3f}</td></tr>
<tr><th>Recall</th><td>{result.recall:.3f}</td></tr>
<tr><th>Average signals per item</th><td>{result.average_signals_per_item:.3f}</td></tr>
<tr><th>Evidence span validity</th><td>{result.evidence_span_validity:.3f}</td></tr>
<tr><th>False positives</th><td>{result.false_positive}</td></tr>
<tr><th>False negatives</th><td>{result.false_negative}</td></tr>
</table>
</section>
<section>
<h2>Signal type coverage</h2>
<table>
<tr><th>Signal type</th><th>Count</th></tr>
{rows}
</table>
</section>
<p>Candidate generation is recall-oriented and does not represent final pain approval.</p>
</body>
</html>"""


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
