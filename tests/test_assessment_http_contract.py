from __future__ import annotations

import json
from typing import Any

import pytest

from painfinder.ai_review_http import ReviewerProfile
from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import SourceItem, SourceType
from painfinder.pain_assessment import (
    AssessmentVerdict,
    PainAssessment,
    build_assessment_requests,
)
from painfinder.pain_assessment_http import HTTPPainAssessor


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_http_assessor_prompt_states_cross_field_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = SourceItem(
        external_id="one",
        source_type=SourceType.POST,
        title="",
        body="We keep doing this manually every week.",
        subreddit="smallbusiness",
        canonical_url="https://reddit.com/one",
    )
    request = build_assessment_requests(
        [item],
        generate_candidate_signals([item]),
    )[0]
    response = PainAssessment(
        source_external_id="one",
        verdict=AssessmentVerdict.NOT_PAIN,
        pain_confidence=0.1,
        evidence_confidence=0.8,
        rationale="The candidate wording does not establish a concrete problem.",
    )
    captured: list[Any] = []

    def fake_urlopen(http_request: Any, timeout: float) -> _Response:
        captured.append(http_request)
        return _Response(
            {
                "choices": [
                    {"message": {"content": response.model_dump_json()}}
                ]
            }
        )

    monkeypatch.setattr(
        "painfinder.ai_review_http.urllib.request.urlopen",
        fake_urlopen,
    )
    profile = ReviewerProfile(
        name="assessor",
        endpoint="http://127.0.0.1:11434/v1/chat/completions",
        model="local-model",
        system_prompt="Return grounded JSON.",
        retries=0,
    )

    HTTPPainAssessor(profile).assess(request)

    payload = json.loads(captured[0].data.decode("utf-8"))
    prompt = payload["messages"][1]["content"]
    assert 'verdict="pain" requires at least one allowed category' in prompt
    assert (
        'verdict="not_pain" or verdict="abstain" requires categories=[]'
        in prompt
    )
    assert 'Never return verdict="pain" with an empty categories array.' in prompt
