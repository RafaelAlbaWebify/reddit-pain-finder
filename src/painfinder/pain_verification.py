from __future__ import annotations

import json
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from painfinder.domain import EvidenceSpan, PainCategory
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    PainAssessmentRequest,
)


class VerificationVerdict(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"
    ABSTAIN = "abstain"


class VerificationReason(StrEnum):
    SUPPORTED_BY_SOURCE = "supported_by_source"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    ADVICE_ONLY = "advice_only"
    PROMOTIONAL_OR_SELF_INTERESTED = "promotional_or_self_interested"
    HYPOTHETICAL_OR_GENERAL = "hypothetical_or_general"
    QUOTED_OR_SECOND_HAND = "quoted_or_second_hand"
    CONTRADICTED_BY_SOURCE = "contradicted_by_source"
    CATEGORY_MISMATCH = "category_mismatch"
    PROBLEM_STATEMENT_OVERREACH = "problem_statement_overreach"
    EVIDENCE_MISMATCH = "evidence_mismatch"


class PainVerificationRequest(BaseModel):
    assessment_request: PainAssessmentRequest
    assessment: PainAssessment

    @model_validator(mode="after")
    def validate_assessment_binding(self) -> PainVerificationRequest:
        expected_id = self.assessment_request.item.external_id
        if self.assessment.source_external_id != expected_id:
            raise ValueError("assessment belongs to another source item")
        return self


class PainVerification(BaseModel):
    source_external_id: str = Field(min_length=1)
    verdict: VerificationVerdict
    verification_confidence: float = Field(ge=0.0, le=1.0)
    evidence_confidence: float = Field(ge=0.0, le=1.0)
    reasons: tuple[VerificationReason, ...] = Field(min_length=1)
    confirmed_categories: tuple[PainCategory, ...] = ()
    corrected_problem_statement: str = ""
    rationale: str = Field(min_length=1)
    cited_evidence: tuple[EvidenceSpan, ...] = ()

    @field_validator("reasons")
    @classmethod
    def normalize_reasons(
        cls,
        value: tuple[VerificationReason, ...],
    ) -> tuple[VerificationReason, ...]:
        return tuple(sorted(set(value), key=lambda reason: reason.value))

    @field_validator("confirmed_categories")
    @classmethod
    def normalize_categories(
        cls,
        value: tuple[PainCategory, ...],
    ) -> tuple[PainCategory, ...]:
        return tuple(sorted(set(value), key=lambda category: category.value))

    @model_validator(mode="after")
    def enforce_verdict_contract(self) -> PainVerification:
        corrected = self.corrected_problem_statement.strip()

        if self.verdict is VerificationVerdict.CONFIRM:
            if not self.confirmed_categories:
                raise ValueError("confirm verdict requires confirmed categories")
            if not self.cited_evidence:
                raise ValueError("confirm verdict requires cited evidence")
            if VerificationReason.SUPPORTED_BY_SOURCE not in self.reasons:
                raise ValueError("confirm verdict requires supported_by_source")
        else:
            if self.confirmed_categories:
                raise ValueError(
                    "reject or abstain verdict cannot confirm categories"
                )
            if corrected:
                raise ValueError(
                    "reject or abstain verdict cannot correct problem statement"
                )

        if (
            self.verdict is VerificationVerdict.REJECT
            and VerificationReason.SUPPORTED_BY_SOURCE in self.reasons
        ):
            raise ValueError("reject verdict cannot claim source support")

        return self


class PainVerifier(Protocol):
    def verify(self, request: PainVerificationRequest) -> PainVerification:
        """Return one skeptical verification for an assessment."""


def run_verifications(
    requests: tuple[PainVerificationRequest, ...],
    verifier: PainVerifier,
) -> tuple[PainVerification, ...]:
    verifications: list[PainVerification] = []
    seen_ids: set[str] = set()

    for request in requests:
        verification = verifier.verify(request)
        expected_id = request.assessment_request.item.external_id
        if verification.source_external_id != expected_id:
            raise ValueError(
                f"verifier returned {verification.source_external_id} "
                f"for candidate {expected_id}"
            )
        if expected_id in seen_ids:
            raise ValueError(f"duplicate verification: {expected_id}")
        _validate_verification_evidence(request, verification)
        _validate_verification_semantics(request, verification)
        verifications.append(verification)
        seen_ids.add(expected_id)

    return tuple(verifications)


def verification_prompt_payload(request: PainVerificationRequest) -> str:
    return json.dumps(
        {
            "task": (
                "Skeptically verify the pain assessment. Do not repeat the "
                "assessment by default. Search for ambiguity, advice-only "
                "content, promotional intent, hypothetical framing, quoted "
                "claims, category mismatch, and problem-statement overreach."
            ),
            "verdicts": {
                "confirm": (
                    "Use only when the source and candidate evidence directly "
                    "support the assessment."
                ),
                "reject": (
                    "Use when the assessment is materially wrong or overclaims."
                ),
                "abstain": (
                    "Use when evidence is too ambiguous for confirm or reject."
                ),
            },
            "source": request.assessment_request.item.model_dump(mode="json"),
            "candidate_signals": [
                signal.model_dump(mode="json")
                for signal in request.assessment_request.candidate_signals
            ],
            "assessment": request.assessment.model_dump(mode="json"),
            "allowed_reasons": [
                reason.value for reason in VerificationReason
            ],
        },
        separators=(",", ":"),
    )


def _validate_verification_evidence(
    request: PainVerificationRequest,
    verification: PainVerification,
) -> None:
    available_spans = {
        (
            span.field,
            span.start,
            span.end,
            span.text,
        )
        for signal in request.assessment_request.candidate_signals
        for span in signal.evidence_spans
    }
    for span in verification.cited_evidence:
        key = (span.field, span.start, span.end, span.text)
        if key not in available_spans:
            raise ValueError(
                "verification cites evidence absent from candidate signals"
            )


def _validate_verification_semantics(
    request: PainVerificationRequest,
    verification: PainVerification,
) -> None:
    assessment = request.assessment

    if (
        assessment.verdict is not AssessmentVerdict.PAIN
        and verification.verdict is VerificationVerdict.CONFIRM
    ):
        raise ValueError(
            "confirm verification is only valid for a pain assessment"
        )

    if (
        verification.verdict is VerificationVerdict.CONFIRM
        and not set(verification.confirmed_categories).issubset(
            set(assessment.categories)
        )
    ):
        raise ValueError(
            "verification cannot add categories absent from assessment"
        )
