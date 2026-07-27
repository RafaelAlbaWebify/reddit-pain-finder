from __future__ import annotations

import json
from typing import Any

import pytest

from painfinder.ai_review_http import ReviewerProfile
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import PainCategory, SourceItem, SourceType
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    build_assessment_requests,
    run_assessments,
)
from painfinder.pain_assessment_http import HTTPPainAssessor
from painfinder.pain_verification import (
    PainVerification,
    PainVerificationRequest,
    VerificationReason,
    VerificationVerdict,
    run_verifications,
)
from painfinder.pain_verification_http import HTTPPainVerifier
from painfinder.structured_ai_http import StructuredAIHTTPError


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _item() -> SourceItem:
    return SourceItem(
        external_id="one",
        source_type=SourceType.POST,
        title="",
        body="We are overwhelmed.",
        subreddit="smallbusiness",
        canonical_url="https://reddit.com/one",
    )


def _profile(*, remote: bool = False) -> ReviewerProfile:
    return ReviewerProfile(
        name="structured",
        endpoint=(
            "https://example.com/v1/chat/completions"
            if remote
            else "http://127.0.0.1:11434/v1/chat/completions"
        ),
        model="local-model",
        api_key_env=None,
        system_prompt="Return only grounded structured output.",
        retries=0,
        reasoning_effort="none",
    )


def _completion(model: PainAssessment | PainVerification) -> dict[str, Any]:
    return _completion_content(model.model_dump_json())


def _completion_content(content: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                }
            }
        ]
    }


def test_http_assessor_rebinds_trusted_id_and_uses_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_assessment_requests(
        [_item()],
        generate_candidate_signals([_item()]),
    )[0]
    signal = request.candidate_signals[0]
    captured: list[Any] = []
    response = PainAssessment(
        source_external_id="wrong",
        verdict=AssessmentVerdict.PAIN,
        pain_confidence=0.9,
        evidence_confidence=0.9,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is overloaded.",
        rationale="The source explicitly reports overload.",
        cited_signal_types=(signal.signal_type,),
        cited_evidence=signal.evidence_spans,
    )

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        captured.append(request)
        return _Response(_completion(response))

    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        fake_urlopen,
    )

    result = run_assessments((request,), HTTPPainAssessor(_profile()))

    assert result[0].source_external_id == "one"
    payload = json.loads(captured[0].data.decode("utf-8"))
    assert payload["response_format"]["json_schema"]["name"] == (
        "painfinder_pain_assessment"
    )
    assert payload["reasoning_effort"] == "none"
    prompt = payload["messages"][1]["content"]
    assert 'verdict="pain" requires at least one allowed category' in prompt
    assert (
        'verdict="not_pain" or verdict="abstain" requires categories=[]'
        in prompt
    )
    assert 'Never return verdict="pain" with an empty categories array.' in prompt


def test_http_verifier_rebinds_trusted_id_and_confirms_grounded_assessment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_request = build_assessment_requests(
        [_item()],
        generate_candidate_signals([_item()]),
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
    request = PainVerificationRequest(
        assessment_request=assessment_request,
        assessment=assessment,
    )
    response = PainVerification(
        source_external_id="wrong",
        verdict=VerificationVerdict.CONFIRM,
        verification_confidence=0.9,
        evidence_confidence=0.9,
        reasons=(VerificationReason.SUPPORTED_BY_SOURCE,),
        confirmed_categories=(PainCategory.RELIABILITY,),
        corrected_problem_statement="The team is overloaded.",
        rationale="The source supports the assessment.",
        cited_evidence=signal.evidence_spans,
    )
    captured: list[Any] = []

    def fake_urlopen(http_request: Any, timeout: float) -> _Response:
        captured.append(http_request)
        return _Response(_completion(response))

    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        fake_urlopen,
    )

    result = run_verifications((request,), HTTPPainVerifier(_profile()))

    assert result[0].source_external_id == "one"
    assert result[0].verdict is VerificationVerdict.CONFIRM
    payload = json.loads(captured[0].data.decode("utf-8"))
    prompt = payload["messages"][1]["content"]
    assert 'verdict="confirm" requires at least one confirmed category' in prompt
    assert (
        'verdict="reject" or verdict="abstain" requires '
        "confirmed_categories=[]" in prompt
    )
    assert 'verdict="reject" must not include reason="supported_by_source"' in prompt


def test_semantic_validation_failure_gets_one_grounded_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_assessment_requests(
        [_item()],
        generate_candidate_signals([_item()]),
    )[0]
    signal = request.candidate_signals[0]
    invalid_content = json.dumps(
        {
            "source_external_id": "wrong",
            "verdict": "pain",
            "pain_confidence": 0.9,
            "evidence_confidence": 0.9,
            "categories": [],
            "problem_statement": "The team is overloaded.",
            "rationale": "The source explicitly reports overload.",
            "cited_signal_types": [signal.signal_type.value],
            "cited_evidence": [
                span.model_dump(mode="json") for span in signal.evidence_spans
            ],
        }
    )
    repaired = PainAssessment(
        source_external_id="wrong",
        verdict=AssessmentVerdict.PAIN,
        pain_confidence=0.9,
        evidence_confidence=0.9,
        categories=(PainCategory.RELIABILITY,),
        problem_statement="The team is overloaded.",
        rationale="The source explicitly reports overload.",
        cited_signal_types=(signal.signal_type,),
        cited_evidence=signal.evidence_spans,
    )
    responses = [
        _Response(_completion_content(invalid_content)),
        _Response(_completion(repaired)),
    ]
    captured: list[Any] = []

    def fake_urlopen(http_request: Any, timeout: float) -> _Response:
        captured.append(http_request)
        return responses.pop(0)

    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        fake_urlopen,
    )

    result = run_assessments((request,), HTTPPainAssessor(_profile()))

    assert result[0].categories == (PainCategory.RELIABILITY,)
    assert len(captured) == 2
    repair_payload = json.loads(captured[1].data.decode("utf-8"))
    assert [message["role"] for message in repair_payload["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert repair_payload["messages"][2]["content"] == invalid_content
    repair_prompt = repair_payload["messages"][3]["content"]
    assert "Change only fields required" in repair_prompt
    assert "Do not invent facts" in repair_prompt
    assert "Schema-specific rules for PainAssessment" in repair_prompt
    assert 'If you cannot provide every required grounded field, set verdict="abstain"' in repair_prompt
    assert 'Never keep verdict="pain" while leaving categories' in repair_prompt
    assert "pain verdict requires at least one category" in repair_prompt


def test_remote_structured_profile_requires_api_key_setting() -> None:
    request = build_assessment_requests(
        [_item()],
        generate_candidate_signals([_item()]),
    )[0]

    with pytest.raises(StructuredAIHTTPError, match="requires api_key_env"):
        HTTPPainAssessor(_profile(remote=True)).assess(request)
