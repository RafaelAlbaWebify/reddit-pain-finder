from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationRecord
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.pain_assessment import AssessmentVerdict
from painfinder.pain_policy import FinalPolicyDecision
from painfinder.pain_verification import VerificationVerdict


class CandidateMissExample(BaseModel):
    source_external_id: str = Field(min_length=1)
    subreddit: str | None = None
    source_type: str
    expected_categories: tuple[str, ...]
    surface_cues: tuple[str, ...]
    text_excerpt: str


class CandidateQualityReport(BaseModel):
    case_count: int
    expected_pain_count: int
    candidate_detected_count: int
    candidate_miss_count: int
    candidate_true_positive: int
    candidate_false_positive: int
    candidate_true_negative: int
    candidate_false_negative: int
    candidate_precision: float
    candidate_recall: float
    misses_by_expected_category: dict[str, int]
    misses_by_subreddit: dict[str, int]
    misses_by_source_type: dict[str, int]
    misses_by_surface_cue: dict[str, int]
    candidate_false_positive_ids: tuple[str, ...]
    candidate_miss_ids: tuple[str, ...]
    candidate_miss_examples: tuple[CandidateMissExample, ...]
    record_count: int
    missing_record_count: int
    assessor_pain_count: int
    assessor_abstain_count: int
    verifier_confirm_count: int
    verifier_abstain_count: int
    final_accept_count: int
    final_review_count: int
    final_reject_count: int
    policy_reason_counts: dict[str, int]


def analyze_candidate_quality(
    cases: list[BenchmarkCase],
    records: dict[str, CalibrationRecord],
    *,
    example_limit: int = 20,
) -> CandidateQualityReport:
    signals = generate_candidate_signals([case.item for case in cases])
    detected_ids = {signal.source_external_id for signal in signals}

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    miss_ids: list[str] = []
    false_positive_ids: list[str] = []
    misses_by_category: Counter[str] = Counter()
    misses_by_subreddit: Counter[str] = Counter()
    misses_by_source_type: Counter[str] = Counter()
    misses_by_surface_cue: Counter[str] = Counter()
    examples: list[CandidateMissExample] = []

    for case in sorted(cases, key=lambda value: value.item.external_id):
        detected = case.item.external_id in detected_ids
        if case.expected_pain and detected:
            true_positive += 1
        elif case.expected_pain:
            false_negative += 1
            miss_ids.append(case.item.external_id)
            categories = tuple(category.value for category in case.expected_categories)
            misses_by_category.update(categories or ("<unlabelled>",))
            misses_by_subreddit[case.item.subreddit or "<none>"] += 1
            misses_by_source_type[case.item.source_type.value] += 1
            cues = _surface_cues(case.item.title, case.item.body)
            misses_by_surface_cue.update(cues or ("<no_common_cue>",))
            if len(examples) < example_limit:
                examples.append(
                    CandidateMissExample(
                        source_external_id=case.item.external_id,
                        subreddit=case.item.subreddit,
                        source_type=case.item.source_type.value,
                        expected_categories=categories,
                        surface_cues=cues,
                        text_excerpt=_excerpt(case.item.title, case.item.body),
                    )
                )
        elif detected:
            false_positive += 1
            false_positive_ids.append(case.item.external_id)
        else:
            true_negative += 1

    assessor_pain = 0
    assessor_abstain = 0
    verifier_confirm = 0
    verifier_abstain = 0
    final_counts: Counter[str] = Counter()
    policy_reason_counts: Counter[str] = Counter()
    missing_record_count = 0

    for case in cases:
        record = records.get(case.item.external_id)
        if record is None:
            missing_record_count += 1
            continue
        if record.assessment is not None:
            if record.assessment.verdict is AssessmentVerdict.PAIN:
                assessor_pain += 1
            elif record.assessment.verdict is AssessmentVerdict.ABSTAIN:
                assessor_abstain += 1
        if record.verification is not None:
            if record.verification.verdict is VerificationVerdict.CONFIRM:
                verifier_confirm += 1
            elif record.verification.verdict is VerificationVerdict.ABSTAIN:
                verifier_abstain += 1
        if record.decision is not None:
            final_counts[record.decision.value] += 1
        if record.policy_outcome is not None:
            policy_reason_counts.update(
                reason.value for reason in record.policy_outcome.reasons
            )

    return CandidateQualityReport(
        case_count=len(cases),
        expected_pain_count=sum(case.expected_pain for case in cases),
        candidate_detected_count=len(detected_ids),
        candidate_miss_count=false_negative,
        candidate_true_positive=true_positive,
        candidate_false_positive=false_positive,
        candidate_true_negative=true_negative,
        candidate_false_negative=false_negative,
        candidate_precision=_ratio(true_positive, true_positive + false_positive),
        candidate_recall=_ratio(true_positive, true_positive + false_negative),
        misses_by_expected_category=dict(sorted(misses_by_category.items())),
        misses_by_subreddit=dict(sorted(misses_by_subreddit.items())),
        misses_by_source_type=dict(sorted(misses_by_source_type.items())),
        misses_by_surface_cue=dict(sorted(misses_by_surface_cue.items())),
        candidate_false_positive_ids=tuple(sorted(false_positive_ids)),
        candidate_miss_ids=tuple(sorted(miss_ids)),
        candidate_miss_examples=tuple(examples),
        record_count=len(records),
        missing_record_count=missing_record_count,
        assessor_pain_count=assessor_pain,
        assessor_abstain_count=assessor_abstain,
        verifier_confirm_count=verifier_confirm,
        verifier_abstain_count=verifier_abstain,
        final_accept_count=final_counts[FinalPolicyDecision.ACCEPT.value],
        final_review_count=final_counts[FinalPolicyDecision.REVIEW.value],
        final_reject_count=final_counts[FinalPolicyDecision.REJECT.value],
        policy_reason_counts=dict(sorted(policy_reason_counts.items())),
    )


def write_candidate_quality_report(
    report: CandidateQualityReport,
    *,
    json_output: Path,
    markdown_output: Path,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown_report(report), encoding="utf-8")


def _markdown_report(report: CandidateQualityReport) -> str:
    category_rows = _counter_rows(report.misses_by_expected_category)
    subreddit_rows = _counter_rows(report.misses_by_subreddit)
    cue_rows = _counter_rows(report.misses_by_surface_cue)
    examples = "\n".join(
        f"- `{example.source_external_id}` — {example.subreddit or '<none>'}; "
        f"categories: {', '.join(example.expected_categories) or '<none>'}; "
        f"cues: {', '.join(example.surface_cues) or '<none>'}; "
        f"excerpt: {example.text_excerpt}"
        for example in report.candidate_miss_examples
    ) or "- None"
    return f"""# Candidate quality analysis

## Candidate-stage baseline

| Metric | Value |
|---|---:|
| Cases | {report.case_count} |
| Expected pain cases | {report.expected_pain_count} |
| Candidate-detected cases | {report.candidate_detected_count} |
| Candidate misses | {report.candidate_miss_count} |
| Candidate precision | {report.candidate_precision:.4f} |
| Candidate recall | {report.candidate_recall:.4f} |
| Candidate false positives | {report.candidate_false_positive} |

## Misses by expected category

{category_rows}

## Misses by subreddit

{subreddit_rows}

## Misses by surface cue

{cue_rows}

## Review funnel

| Stage | Count |
|---|---:|
| Assessor pain | {report.assessor_pain_count} |
| Assessor abstain | {report.assessor_abstain_count} |
| Verifier confirm | {report.verifier_confirm_count} |
| Verifier abstain | {report.verifier_abstain_count} |
| Final accept | {report.final_accept_count} |
| Final review | {report.final_review_count} |
| Final reject | {report.final_reject_count} |

## Representative candidate misses

{examples}

This report is descriptive. It does not change detector rules, policy thresholds, or gold labels.
"""


def _counter_rows(values: dict[str, int]) -> str:
    if not values:
        return "| Value | Count |\n|---|---:|\n| None | 0 |"
    rows = "\n".join(
        f"| {name} | {count} |"
        for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))
    )
    return f"| Value | Count |\n|---|---:|\n{rows}"


def _surface_cues(title: str, body: str) -> tuple[str, ...]:
    text = f"{title}\n{body}".lower()
    patterns = {
        "question": (
            r"\?|\b(?:how|what|why|which|where|who|does|do|is|are|can|should)\b"
        ),
        "first_person_difficulty": (
            r"\b(?:i|we)\b.{0,40}"
            r"\b(?:can't|cannot|struggl|stuck|unable|hard|difficult)\b"
        ),
        "negative_outcome": (
            r"\b(?:lost|losing|failed|failure|worse|slow|late|blocked|broken|problem)\b"
        ),
        "financial": (
            r"\b(?:cost|price|budget|money|revenue|payment|expensive|afford)\b"
        ),
        "manual_or_time": (
            r"\b(?:manual|spreadsheet|hours|time[- ]consuming|repetitive|by hand)\b"
        ),
        "request_or_search": (
            r"\b(?:need|looking for|recommend|advice|solution|alternative)\b"
        ),
    }
    return tuple(name for name, pattern in patterns.items() if re.search(pattern, text))


def _excerpt(title: str, body: str, limit: int = 220) -> str:
    text = " ".join(part.strip() for part in (title, body) if part.strip())
    compact = re.sub(r"\s+", " ", text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
