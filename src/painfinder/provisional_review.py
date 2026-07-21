from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from painfinder.analysis import detect_pain_signals
from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.domain import PainCategory, SourceItem


class ProvisionalReviewError(RuntimeError):
    pass


class ReviewerDecision(BaseModel):
    external_id: str = Field(min_length=1)
    expected_pain: bool
    expected_categories: tuple[PainCategory, ...] = ()
    expected_cluster: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)

    @field_validator("expected_categories")
    @classmethod
    def normalize_categories(
        cls,
        value: tuple[PainCategory, ...],
    ) -> tuple[PainCategory, ...]:
        return tuple(sorted(set(value), key=lambda category: category.value))


@dataclass(frozen=True)
class ConsensusSummary:
    item_count: int
    provisional_count: int
    approval_queue_count: int
    unanimous_count: int
    majority_count: int
    disputed_count: int
    low_confidence_count: int
    audit_sample_count: int
    detector_conflict_count: int


def build_provisional_review(
    blind_packet: Path,
    reviewer_outputs: tuple[Path, Path, Path],
    *,
    provisional_output: Path,
    approval_queue_output: Path,
    summary_output: Path,
    minimum_confidence: float = 0.8,
    audit_percent: int = 10,
) -> ConsensusSummary:
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ProvisionalReviewError("minimum_confidence must be between 0 and 1")
    if not 0 <= audit_percent <= 100:
        raise ProvisionalReviewError("audit_percent must be between 0 and 100")

    evidence = _load_blind_packet(blind_packet)
    detector_predictions = _detector_predictions(evidence)
    reviews = [_load_reviewer_output(path) for path in reviewer_outputs]
    expected_ids = set(evidence)
    for index, reviewer in enumerate(reviews, start=1):
        if set(reviewer) != expected_ids:
            missing = sorted(expected_ids - set(reviewer))
            extra = sorted(set(reviewer) - expected_ids)
            raise ProvisionalReviewError(
                f"Reviewer {index} evidence IDs differ; missing={missing}, extra={extra}"
            )

    provisional_rows: list[dict[str, str]] = []
    queue_rows: list[dict[str, str]] = []
    unanimous_count = 0
    majority_count = 0
    disputed_count = 0
    low_confidence_count = 0
    audit_sample_count = 0
    detector_conflict_count = 0

    for external_id in sorted(evidence):
        decisions = [reviewer[external_id] for reviewer in reviews]
        consensus, agreement = _consensus(decisions)
        mean_confidence = sum(decision.confidence for decision in decisions) / len(decisions)
        low_confidence = mean_confidence < minimum_confidence
        audit_sample = _in_audit_sample(external_id, audit_percent)
        detector_pain, detector_categories = detector_predictions[external_id]
        detector_conflict = (
            consensus.expected_pain != detector_pain
            or set(consensus.expected_categories) != detector_categories
        )
        reasons: list[str] = []

        if agreement == "unanimous":
            unanimous_count += 1
        elif agreement == "majority":
            majority_count += 1
            reasons.append("reviewer_disagreement")
        else:
            disputed_count += 1
            reasons.append("disputed")
        if low_confidence:
            low_confidence_count += 1
            reasons.append("low_confidence")
        if audit_sample:
            audit_sample_count += 1
            reasons.append("audit_sample")
        if detector_conflict:
            detector_conflict_count += 1
            reasons.append("detector_conflict")

        source = evidence[external_id]
        row = _output_row(
            source,
            consensus,
            decisions,
            agreement,
            mean_confidence,
            reasons,
            detector_pain,
            detector_categories,
        )
        if reasons:
            queue_rows.append(row)
        else:
            provisional_rows.append(row)

    _write_rows(provisional_output, provisional_rows)
    _write_rows(approval_queue_output, queue_rows)
    summary = ConsensusSummary(
        item_count=len(evidence),
        provisional_count=len(provisional_rows),
        approval_queue_count=len(queue_rows),
        unanimous_count=unanimous_count,
        majority_count=majority_count,
        disputed_count=disputed_count,
        low_confidence_count=low_confidence_count,
        audit_sample_count=audit_sample_count,
        detector_conflict_count=detector_conflict_count,
    )
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")
    return summary


def _load_blind_packet(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_COLUMNS:
            raise ProvisionalReviewError("Blind packet has unexpected columns")
        rows = list(reader)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        normalized = {column: row.get(column) or "" for column in REVIEW_COLUMNS}
        external_id = normalized["external_id"].strip()
        if not external_id or external_id in result:
            raise ProvisionalReviewError("Blind packet IDs must be non-empty and unique")
        result[external_id] = normalized
    if not result:
        raise ProvisionalReviewError("Blind packet is empty")
    return result


def _detector_predictions(
    evidence: dict[str, dict[str, str]],
) -> dict[str, tuple[bool, set[PainCategory]]]:
    items: list[SourceItem] = []
    try:
        for external_id in sorted(evidence):
            row = evidence[external_id]
            items.append(
                SourceItem.model_validate(
                    {
                        "external_id": external_id,
                        "source_type": row["source_type"],
                        "title": row["title"],
                        "body": row["body"],
                        "subreddit": row["community"] or None,
                        "canonical_url": row["canonical_url"],
                    }
                )
            )
    except ValidationError as error:
        raise ProvisionalReviewError(f"Blind packet contains invalid evidence: {error}") from error

    categories_by_id: dict[str, set[PainCategory]] = {
        item.external_id: set() for item in items
    }
    for signal in detect_pain_signals(items):
        categories_by_id[signal.source_external_id].add(signal.category)
    return {
        external_id: (bool(categories), categories)
        for external_id, categories in categories_by_id.items()
    }


def _load_reviewer_output(path: Path) -> dict[str, ReviewerDecision]:
    result: dict[str, ReviewerDecision] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue
        try:
            decision = ReviewerDecision.model_validate_json(raw_line)
        except ValueError as error:
            raise ProvisionalReviewError(
                f"Invalid reviewer JSONL at {path}:{line_number}: {error}"
            ) from error
        if decision.external_id in result:
            raise ProvisionalReviewError(
                f"Duplicate reviewer evidence ID in {path}: {decision.external_id}"
            )
        result[decision.external_id] = decision
    return result


def _decision_key(decision: ReviewerDecision) -> tuple[Any, ...]:
    return (
        decision.expected_pain,
        tuple(category.value for category in decision.expected_categories),
        decision.expected_cluster.strip(),
    )


def _consensus(
    decisions: list[ReviewerDecision],
) -> tuple[ReviewerDecision, str]:
    counts = Counter(_decision_key(decision) for decision in decisions)
    key, count = counts.most_common(1)[0]
    matching = [decision for decision in decisions if _decision_key(decision) == key]
    representative = max(matching, key=lambda decision: decision.confidence)
    if count == 3:
        return representative, "unanimous"
    if count == 2:
        return representative, "majority"
    return representative, "disputed"


def _in_audit_sample(external_id: str, audit_percent: int) -> bool:
    if audit_percent <= 0:
        return False
    bucket = int(hashlib.sha256(external_id.encode()).hexdigest()[:8], 16) % 100
    return bucket < audit_percent


def _output_row(
    source: dict[str, str],
    consensus: ReviewerDecision,
    decisions: list[ReviewerDecision],
    agreement: str,
    mean_confidence: float,
    reasons: list[str],
    detector_pain: bool,
    detector_categories: set[PainCategory],
) -> dict[str, str]:
    return {
        **{column: source[column] for column in REVIEW_COLUMNS[:6]},
        "expected_pain": str(consensus.expected_pain).lower(),
        "expected_categories": ",".join(
            category.value for category in consensus.expected_categories
        ),
        "expected_cluster": consensus.expected_cluster,
        "review_status": "provisional",
        "reviewer": "ai_consensus",
        "reviewed_at": "",
        "rationale": consensus.rationale,
        "agreement": agreement,
        "mean_confidence": f"{mean_confidence:.3f}",
        "escalation_reasons": ",".join(reasons),
        "reviewer_decisions": json.dumps(
            [decision.model_dump(mode="json") for decision in decisions],
            separators=(",", ":"),
        ),
        "detector_pain": str(detector_pain).lower(),
        "detector_categories": ",".join(
            category.value for category in sorted(
                detector_categories,
                key=lambda value: value.value,
            )
        ),
        "human_decision": "",
        "human_reviewer": "",
        "human_reviewed_at": "",
        "human_rationale": "",
    }


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    columns = (
        *REVIEW_COLUMNS,
        "agreement",
        "mean_confidence",
        "escalation_reasons",
        "reviewer_decisions",
        "detector_pain",
        "detector_categories",
        "human_decision",
        "human_reviewer",
        "human_reviewed_at",
        "human_rationale",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
