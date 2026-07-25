from __future__ import annotations

import json
from collections.abc import Iterable
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from painfinder.domain import (
    CandidateSignal,
    EvidenceField,
    EvidenceSpan,
    PainCategory,
    SignalType,
    SourceItem,
)


class AssessmentVerdict(StrEnum):
    PAIN = "pain"
    NOT_PAIN = "not_pain"
    ABSTAIN = "abstain"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PainAssessmentRequest(BaseModel):
    item: SourceItem
    candidate_signals: tuple[CandidateSignal, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate_evidence(self) -> PainAssessmentRequest:
        for signal in self.candidate_signals:
            if signal.source_external_id != self.item.external_id:
                raise ValueError("candidate signal belongs to another source item")
            for span in signal.evidence_spans:
                _validate_span(self.item, span)
        return self

    @field_validator("candidate_signals")
    @classmethod
    def normalize_candidate_signals(
        cls,
        value: tuple[CandidateSignal, ...],
    ) -> tuple[CandidateSignal, ...]:
        return tuple(
            sorted(
                value,
                key=lambda signal: (
                    signal.signal_type.value,
                    signal.detector_id,
                    signal.evidence_spans[0].field.value,
                    signal.evidence_spans[0].start,
                ),
            )
        )


class PainAssessment(BaseModel):
    source_external_id: str = Field(min_length=1)
    verdict: AssessmentVerdict
    pain_confidence: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    categories: tuple[PainCategory, ...] = ()
    problem_statement: str = ""
    rationale: str = Field(min_length=1)
    cited_signal_types: tuple[SignalType, ...] = ()
    cited_evidence: tuple[EvidenceSpan, ...] = ()

    @field_validator("categories")
    @classmethod
    def normalize_categories(
        cls,
        value: tuple[PainCategory, ...],
    ) -> tuple[PainCategory, ...]:
        return tuple(sorted(set(value), key=lambda category: category.value))

    @field_validator("cited_signal_types")
    @classmethod
    def normalize_signal_types(
        cls,
        value: tuple[SignalType, ...],
    ) -> tuple[SignalType, ...]:
        return tuple(sorted(set(value), key=lambda signal_type: signal_type.value))

    @model_validator(mode="after")
    def enforce_verdict_contract(self) -> PainAssessment:
        statement = self.problem_statement.strip()
        if self.verdict is AssessmentVerdict.PAIN:
            if not self.categories:
                raise ValueError("pain verdict requires at least one category")
            if not statement:
                raise ValueError("pain verdict requires a problem statement")
            if not self.cited_signal_types or not self.cited_evidence:
                raise ValueError("pain verdict requires cited signals and evidence")
        else:
            if self.categories:
                raise ValueError("non-pain verdict cannot assign pain categories")
            if statement:
                raise ValueError("non-pain verdict cannot include a problem statement")
        return self


class PainAssessor(Protocol):
    def assess(self, request: PainAssessmentRequest) -> PainAssessment:
        """Return one structured assessment for the supplied candidate."""


def build_assessment_requests(
    items: Iterable[SourceItem],
    signals: Iterable[CandidateSignal],
) -> tuple[PainAssessmentRequest, ...]:
    items_by_id = {item.external_id: item for item in items}
    signals_by_id: dict[str, list[CandidateSignal]] = {}

    for signal in signals:
        if signal.source_external_id not in items_by_id:
            raise ValueError(
                f"candidate signal references unknown item: "
                f"{signal.source_external_id}"
            )
        signals_by_id.setdefault(signal.source_external_id, []).append(signal)

    return tuple(
        PainAssessmentRequest(
            item=items_by_id[external_id],
            candidate_signals=tuple(signals_by_id[external_id]),
        )
        for external_id in sorted(signals_by_id)
    )


def run_assessments(
    requests: Iterable[PainAssessmentRequest],
    assessor: PainAssessor,
) -> tuple[PainAssessment, ...]:
    assessments: list[PainAssessment] = []
    seen_ids: set[str] = set()

    for request in requests:
        assessment = assessor.assess(request)
        expected_id = request.item.external_id
        if assessment.source_external_id != expected_id:
            raise ValueError(
                f"assessor returned {assessment.source_external_id} "
                f"for candidate {expected_id}"
            )
        if expected_id in seen_ids:
            raise ValueError(f"duplicate candidate assessment: {expected_id}")
        _validate_assessment_evidence(request, assessment)
        assessments.append(assessment)
        seen_ids.add(expected_id)

    return tuple(assessments)


def assessment_prompt_payload(request: PainAssessmentRequest) -> str:
    return json.dumps(
        {
            "task": (
                "Assess whether this source expresses a real human or business "
                "problem. Return pain, not_pain, or abstain. Treat candidate "
                "signals as leads, not proof."
            ),
            "rules": {
                "pain": (
                    "Use only when the evidence supports an experienced or "
                    "credible problem, constraint, failed outcome, risk, cost, "
                    "manual burden, workaround, or explicit unmet need."
                ),
                "not_pain": (
                    "Use for advice-only replies, promotions, neutral facts, "
                    "success stories, jokes, or hypothetical questions without "
                    "supported pain."
                ),
                "abstain": (
                    "Use when context is insufficient, ambiguous, quoted, or "
                    "the candidate evidence does not justify either decision."
                ),
                "confidence_axes": [
                    "pain_confidence",
                    "evidence_confidence",
                ],
                "allowed_categories": [
                    category.value for category in PainCategory
                ],
            },
            "source": request.item.model_dump(mode="json"),
            "candidate_signals": [
                signal.model_dump(mode="json")
                for signal in request.candidate_signals
            ],
        },
        separators=(",", ":"),
    )


def _validate_assessment_evidence(
    request: PainAssessmentRequest,
    assessment: PainAssessment,
) -> None:
    available_types = {
        signal.signal_type for signal in request.candidate_signals
    }
    if not set(assessment.cited_signal_types).issubset(available_types):
        raise ValueError("assessment cites unavailable candidate signal types")

    available_spans = {
        (
            span.field,
            span.start,
            span.end,
            span.text,
        )
        for signal in request.candidate_signals
        for span in signal.evidence_spans
    }
    for span in assessment.cited_evidence:
        _validate_span(request.item, span)
        key = (span.field, span.start, span.end, span.text)
        if key not in available_spans:
            raise ValueError("assessment cites evidence absent from candidates")


def _validate_span(item: SourceItem, span: EvidenceSpan) -> None:
    source = item.title if span.field is EvidenceField.TITLE else item.body
    if source[span.start : span.end] != span.text:
        raise ValueError("evidence span does not match source text")
