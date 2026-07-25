from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import PainCategory, SourceItem, SourceType
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    build_assessment_requests,
)
from painfinder.pain_verification import (
    PainVerification,
    PainVerificationRequest,
    VerificationReason,
    VerificationVerdict,
    run_verifications,
    verification_prompt_payload,
)


def _item(external_id: str, body: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title="",
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


def _pain_request() -> PainVerificationRequest:
    item = _item("one", "We are overwhelmed.")
    assessment_request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]
    signal = assessment_request.candidate_signals[0]
    assessment = PainAssessment(
        source_external_id="one",
        verdict=AssessmentVerdict.PAIN,
        pain_confidence=0.9,
        evidence_confidence=0.9,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is overloaded.",
        rationale="The source explicitly reports overload.",
        cited_signal_types=(signal.signal_type,),
        cited_evidence=signal.evidence_spans,
    )
    return PainVerificationRequest(
        assessment_request=assessment_request,
        assessment=assessment,
    )


def test_request_rejects_assessment_for_another_item() -> None:
    request = _pain_request()
    wrong = request.assessment.model_copy(
        update={"source_external_id": "wrong"}
    )

    with pytest.raises(ValidationError, match="another source item"):
        PainVerificationRequest(
            assessment_request=request.assessment_request,
            assessment=wrong,
        )


def test_confirm_requires_supported_source_and_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="requires confirmed categories",
    ):
        PainVerification(
            source_external_id="one",
            verdict=VerificationVerdict.CONFIRM,
            verification_confidence=0.9,
            evidence_confidence=0.9,
            reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
            rationale="Supported.",
        )


def test_run_verifications_accepts_grounded_confirmation() -> None:
    request = _pain_request()
    span = request.assessment.cited_evidence[0]

    class Verifier:
        def verify(
            self,
            request: PainVerificationRequest,
        ) -> PainVerification:
            return PainVerification(
                source_external_id=request.assessment.source_external_id,
                verdict=VerificationVerdict.CONFIRM,
                verification_confidence=0.9,
                evidence_confidence=0.9,
                reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
                confirmed_categories=request.assessment.categories,
                corrected_problem_statement=(
                    request.assessment.problem_statement
                ),
                rationale="The source directly supports the assessment.",
                cited_evidence=(span,),
            )

    result = run_verifications((request,), Verifier())

    assert result[0].verdict is VerificationVerdict.CONFIRM


def test_run_verifications_rejects_added_category() -> None:
    request = _pain_request()
    span = request.assessment.cited_evidence[0]

    class Verifier:
        def verify(
            self,
            request: PainVerificationRequest,
        ) -> PainVerification:
            return PainVerification(
                source_external_id=request.assessment.source_external_id,
                verdict=VerificationVerdict.CONFIRM,
                verification_confidence=0.8,
                evidence_confidence=0.8,
                reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
                confirmed_categories=(PainCategory.COST,),
                corrected_problem_statement="The team has a cost problem.",
                rationale="Incorrectly expands categories.",
                cited_evidence=(span,),
            )

    with pytest.raises(ValueError, match="cannot add categories"):
        run_verifications((request,), Verifier())


def test_run_verifications_rejects_wrong_source_id() -> None:
    request = _pain_request()

    class Verifier:
        def verify(
            self,
            request: PainVerificationRequest,
        ) -> PainVerification:
            return PainVerification(
                source_external_id="wrong",
                verdict=VerificationVerdict.REJECT,
                verification_confidence=0.9,
                evidence_confidence=0.7,
                reasons=(VerificationReason.ADVICE_ONLY,),
                rationale="This is advice only.",
            )

    with pytest.raises(ValueError, match="for candidate one"):
        run_verifications((request,), Verifier())


def test_verification_payload_is_skeptical_and_structured() -> None:
    request = _pain_request()

    payload = json.loads(verification_prompt_payload(request))

    assert payload["assessment"]["source_external_id"] == "one"
    assert "promotional intent" in payload["task"]
    assert "abstain" in payload["verdicts"]


def test_reject_cannot_claim_supported_by_source() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot claim source support",
    ):
        PainVerification(
            source_external_id="one",
            verdict=VerificationVerdict.REJECT,
            verification_confidence=0.9,
            evidence_confidence=0.9,
            reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
            rationale="Contradictory.",
        )
