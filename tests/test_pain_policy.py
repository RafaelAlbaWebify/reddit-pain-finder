from __future__ import annotations

import pytest
from pydantic import ValidationError

from painfinder.domain import (
    EvidenceField,
    EvidenceSpan,
    PainCategory,
    SignalType,
)
from painfinder.pain_assessment import AssessmentVerdict, PainAssessment
from painfinder.pain_policy import (
    FinalPolicyDecision,
    PainPolicy,
    PainPolicyInput,
    PolicyReason,
    apply_pain_policy,
)
from painfinder.pain_verification import (
    PainVerification,
    VerificationReason,
    VerificationVerdict,
)

SPAN = EvidenceSpan(
    field=EvidenceField.BODY,
    start=0,
    end=12,
    text="We are stuck",
)


def _assessment(
    *,
    verdict: AssessmentVerdict = AssessmentVerdict.PAIN,
    pain_confidence: float = 0.9,
    evidence_confidence: float = 0.9,
) -> PainAssessment:
    if verdict is not AssessmentVerdict.PAIN:
        return PainAssessment(
            source_external_id="one",
            verdict=verdict,
            pain_confidence=pain_confidence,
            evidence_confidence=evidence_confidence,
            rationale="No supported pain decision.",
        )

    return PainAssessment(
        source_external_id="one",
        verdict=verdict,
        pain_confidence=pain_confidence,
        evidence_confidence=evidence_confidence,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is blocked.",
        rationale="The source reports a blocked outcome.",
        cited_signal_types=(SignalType.EXPLICIT_PROBLEM,),
        cited_evidence=(SPAN,),
    )


def _verification(
    *,
    verdict: VerificationVerdict = VerificationVerdict.CONFIRM,
    verification_confidence: float = 0.9,
    evidence_confidence: float = 0.9,
    categories: tuple[PainCategory, ...] = (PainCategory.RELIABILITY,),
) -> PainVerification:
    if verdict is not VerificationVerdict.CONFIRM:
        reason = (
            VerificationReason.ADVICE_ONLY
            if verdict is VerificationVerdict.REJECT
            else VerificationReason.INSUFFICIENT_CONTEXT
        )
        return PainVerification(
            source_external_id="one",
            verdict=verdict,
            verification_confidence=verification_confidence,
            evidence_confidence=evidence_confidence,
            reasons=(reason,),
            rationale="The verifier did not confirm the pain.",
        )

    return PainVerification(
        source_external_id="one",
        verdict=verdict,
        verification_confidence=verification_confidence,
        evidence_confidence=evidence_confidence,
        reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
        confirmed_categories=categories,
        corrected_problem_statement="The team is blocked.",
        rationale="The source supports the assessment.",
        cited_evidence=(SPAN,),
    )


def test_policy_accepts_only_high_confidence_confirmation() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(),
            verification=_verification(),
        )
    )

    assert outcome.decision is FinalPolicyDecision.ACCEPT
    assert outcome.reasons == (PolicyReason.VERIFIER_CONFIRMED,)


def test_policy_rejects_assessor_not_pain() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(verdict=AssessmentVerdict.NOT_PAIN),
            verification=_verification(verdict=VerificationVerdict.REJECT),
        )
    )

    assert outcome.decision is FinalPolicyDecision.REJECT
    assert outcome.reasons == (PolicyReason.ASSESSOR_NOT_PAIN,)


def test_policy_routes_assessor_abstention_to_review() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(verdict=AssessmentVerdict.ABSTAIN),
            verification=_verification(verdict=VerificationVerdict.ABSTAIN),
        )
    )

    assert outcome.decision is FinalPolicyDecision.REVIEW
    assert outcome.reasons == (PolicyReason.ASSESSOR_ABSTAINED,)


def test_policy_rejects_verifier_rejection() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(),
            verification=_verification(verdict=VerificationVerdict.REJECT),
        )
    )

    assert outcome.decision is FinalPolicyDecision.REJECT
    assert outcome.reasons == (PolicyReason.VERIFIER_REJECTED,)


def test_policy_routes_low_confidence_to_review() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(
                pain_confidence=0.7,
                evidence_confidence=0.75,
            ),
            verification=_verification(
                verification_confidence=0.6,
                evidence_confidence=0.65,
            ),
        )
    )

    assert outcome.decision is FinalPolicyDecision.REVIEW
    assert set(outcome.reasons) == {
        PolicyReason.LOW_PAIN_CONFIDENCE,
        PolicyReason.LOW_ASSESSOR_EVIDENCE_CONFIDENCE,
        PolicyReason.LOW_VERIFICATION_CONFIDENCE,
        PolicyReason.LOW_VERIFIER_EVIDENCE_CONFIDENCE,
    }


def test_policy_routes_category_disagreement_to_review() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(),
            verification=_verification(categories=(PainCategory.COST,)),
        )
    )

    assert outcome.decision is FinalPolicyDecision.REVIEW
    assert outcome.reasons == (PolicyReason.CATEGORY_DISAGREEMENT,)


def test_policy_thresholds_are_configurable() -> None:
    outcome = apply_pain_policy(
        PainPolicyInput(
            assessment=_assessment(
                pain_confidence=0.7,
                evidence_confidence=0.7,
            ),
            verification=_verification(
                verification_confidence=0.7,
                evidence_confidence=0.7,
            ),
        ),
        policy=PainPolicy(
            minimum_pain_confidence=0.6,
            minimum_assessor_evidence_confidence=0.6,
            minimum_verification_confidence=0.6,
            minimum_verifier_evidence_confidence=0.6,
        ),
    )

    assert outcome.decision is FinalPolicyDecision.ACCEPT


def test_policy_input_rejects_mismatched_source_ids() -> None:
    verification = _verification().model_copy(
        update={"source_external_id": "two"}
    )

    with pytest.raises(ValidationError, match="different source items"):
        PainPolicyInput(
            assessment=_assessment(),
            verification=verification,
        )
