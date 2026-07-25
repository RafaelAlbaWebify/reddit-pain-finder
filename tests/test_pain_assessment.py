from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import (
    EvidenceField,
    EvidenceSpan,
    PainCategory,
    SignalType,
    SourceItem,
    SourceType,
)
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    PainAssessmentRequest,
    assessment_prompt_payload,
    build_assessment_requests,
    run_assessments,
)


def _item(
    external_id: str,
    body: str,
) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title="",
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


def test_build_requests_includes_only_candidate_items() -> None:
    pain = _item(
        "pain",
        "We are buried in manual work and cannot keep up with the backlog.",
    )
    neutral = _item("neutral", "Thanks for sharing.")

    signals = generate_candidate_signals([pain, neutral])
    requests = build_assessment_requests([neutral, pain], signals)

    assert [request.item.external_id for request in requests] == ["pain"]
    assert requests[0].candidate_signals


def test_request_rejects_signal_for_another_item() -> None:
    left = _item("left", "We are overwhelmed.")
    right = _item("right", "We are overwhelmed.")
    signal = generate_candidate_signals([left])[0]

    with pytest.raises(ValidationError, match="another source item"):
        PainAssessmentRequest(
            item=right,
            candidate_signals=(signal,),
        )


def test_assessment_contract_requires_evidence_for_pain() -> None:
    with pytest.raises(
        ValidationError,
        match="requires at least one category",
    ):
        PainAssessment(
            source_external_id="one",
            verdict=AssessmentVerdict.PAIN,
            pain_confidence=0.8,
            evidence_confidence=0.8,
            rationale="The source sounds painful.",
        )


def test_run_assessments_rejects_wrong_source_id() -> None:
    item = _item("one", "We are overwhelmed.")
    request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]

    class WrongAssessor:
        def assess(
            self,
            request: PainAssessmentRequest,
        ) -> PainAssessment:
            return PainAssessment(
                source_external_id="wrong",
                verdict=AssessmentVerdict.ABSTAIN,
                pain_confidence=0.5,
                evidence_confidence=0.5,
                rationale="Insufficient context.",
            )

    with pytest.raises(ValueError, match="for candidate one"):
        run_assessments([request], WrongAssessor())


def test_run_assessments_accepts_grounded_pain_decision() -> None:
    item = _item("one", "We are overwhelmed.")
    request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]
    signal = request.candidate_signals[0]

    class GroundedAssessor:
        def assess(
            self,
            request: PainAssessmentRequest,
        ) -> PainAssessment:
            return PainAssessment(
                source_external_id=request.item.external_id,
                verdict=AssessmentVerdict.PAIN,
                pain_confidence=0.9,
                evidence_confidence=0.85,
                categories=(PainCategory.RELIABILITY,),
                problem_statement="The team is experiencing overload.",
                rationale="The author explicitly reports being overwhelmed.",
                cited_signal_types=(signal.signal_type,),
                cited_evidence=signal.evidence_spans,
            )

    result = run_assessments([request], GroundedAssessor())

    assert result[0].verdict is AssessmentVerdict.PAIN
    assert result[0].categories == (PainCategory.RELIABILITY,)


def test_run_assessments_rejects_uncited_candidate_evidence() -> None:
    item = _item("one", "We are overwhelmed.")
    request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]
    fake_span = EvidenceSpan(
        field=EvidenceField.BODY,
        start=0,
        end=2,
        text="We",
    )

    class UngroundedAssessor:
        def assess(
            self,
            request: PainAssessmentRequest,
        ) -> PainAssessment:
            return PainAssessment(
                source_external_id=request.item.external_id,
                verdict=AssessmentVerdict.PAIN,
                pain_confidence=0.8,
                evidence_confidence=0.8,
                categories=(PainCategory.RELIABILITY,),
                problem_statement="The team is overloaded.",
                rationale="The source describes overload.",
                cited_signal_types=(SignalType.EXPLICIT_PROBLEM,),
                cited_evidence=(fake_span,),
            )

    with pytest.raises(ValueError):
        run_assessments([request], UngroundedAssessor())


def test_prompt_payload_is_structured_and_abstention_aware() -> None:
    item = _item("one", "We are overwhelmed.")
    request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]

    payload = json.loads(assessment_prompt_payload(request))

    assert payload["source"]["external_id"] == "one"
    assert "abstain" in payload["rules"]
    assert payload["candidate_signals"]
