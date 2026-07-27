from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from painfinder.pain_assessment import AssessmentVerdict, PainAssessment
from painfinder.pain_verification import PainVerification, VerificationVerdict


class FinalPolicyDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


class PolicyReason(StrEnum):
    ASSESSOR_NOT_PAIN = "assessor_not_pain"
    ASSESSOR_ABSTAINED = "assessor_abstained"
    VERIFIER_CONFIRMED = "verifier_confirmed"
    VERIFIER_REJECTED = "verifier_rejected"
    VERIFIER_ABSTAINED = "verifier_abstained"
    LOW_PAIN_CONFIDENCE = "low_pain_confidence"
    LOW_ASSESSOR_EVIDENCE_CONFIDENCE = "low_assessor_evidence_confidence"
    LOW_VERIFICATION_CONFIDENCE = "low_verification_confidence"
    LOW_VERIFIER_EVIDENCE_CONFIDENCE = "low_verifier_evidence_confidence"
    CATEGORY_DISAGREEMENT = "category_disagreement"


class PainPolicy(BaseModel):
    minimum_pain_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    minimum_assessor_evidence_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
    )
    minimum_verification_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
    )
    minimum_verifier_evidence_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
    )


class PolicyOutcome(BaseModel):
    source_external_id: str = Field(min_length=1)
    decision: FinalPolicyDecision
    reasons: tuple[PolicyReason, ...] = Field(min_length=1)
    assessor_verdict: AssessmentVerdict
    verifier_verdict: VerificationVerdict


class PainPolicyInput(BaseModel):
    assessment: PainAssessment
    verification: PainVerification

    @model_validator(mode="after")
    def validate_binding(self) -> PainPolicyInput:
        if (
            self.assessment.source_external_id
            != self.verification.source_external_id
        ):
            raise ValueError(
                "assessment and verification belong to different source items"
            )
        return self


def apply_pain_policy(
    policy_input: PainPolicyInput,
    *,
    policy: PainPolicy | None = None,
) -> PolicyOutcome:
    active_policy = policy or PainPolicy()
    assessment = policy_input.assessment
    verification = policy_input.verification
    reasons: list[PolicyReason] = []

    if assessment.verdict is AssessmentVerdict.NOT_PAIN:
        return _outcome(
            assessment,
            verification,
            FinalPolicyDecision.REJECT,
            PolicyReason.ASSESSOR_NOT_PAIN,
        )

    if assessment.verdict is AssessmentVerdict.ABSTAIN:
        return _outcome(
            assessment,
            verification,
            FinalPolicyDecision.REVIEW,
            PolicyReason.ASSESSOR_ABSTAINED,
        )

    if verification.verdict is VerificationVerdict.REJECT:
        return _outcome(
            assessment,
            verification,
            FinalPolicyDecision.REJECT,
            PolicyReason.VERIFIER_REJECTED,
        )

    if verification.verdict is VerificationVerdict.ABSTAIN:
        return _outcome(
            assessment,
            verification,
            FinalPolicyDecision.REVIEW,
            PolicyReason.VERIFIER_ABSTAINED,
        )

    if assessment.pain_confidence < active_policy.minimum_pain_confidence:
        reasons.append(PolicyReason.LOW_PAIN_CONFIDENCE)

    if (
        assessment.evidence_confidence
        < active_policy.minimum_assessor_evidence_confidence
    ):
        reasons.append(PolicyReason.LOW_ASSESSOR_EVIDENCE_CONFIDENCE)

    if (
        verification.verification_confidence
        < active_policy.minimum_verification_confidence
    ):
        reasons.append(PolicyReason.LOW_VERIFICATION_CONFIDENCE)

    if (
        verification.evidence_confidence
        < active_policy.minimum_verifier_evidence_confidence
    ):
        reasons.append(PolicyReason.LOW_VERIFIER_EVIDENCE_CONFIDENCE)

    if set(verification.confirmed_categories) != set(assessment.categories):
        reasons.append(PolicyReason.CATEGORY_DISAGREEMENT)

    if reasons:
        return PolicyOutcome(
            source_external_id=assessment.source_external_id,
            decision=FinalPolicyDecision.REVIEW,
            reasons=tuple(reasons),
            assessor_verdict=assessment.verdict,
            verifier_verdict=verification.verdict,
        )

    return _outcome(
        assessment,
        verification,
        FinalPolicyDecision.ACCEPT,
        PolicyReason.VERIFIER_CONFIRMED,
    )


def _outcome(
    assessment: PainAssessment,
    verification: PainVerification,
    decision: FinalPolicyDecision,
    reason: PolicyReason,
) -> PolicyOutcome:
    return PolicyOutcome(
        source_external_id=assessment.source_external_id,
        decision=decision,
        reasons=(reason,),
        assessor_verdict=assessment.verdict,
        verifier_verdict=verification.verdict,
    )
