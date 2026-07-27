from __future__ import annotations

import json

from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import SourceItem, SourceType
from painfinder.pain_assessment import assessment_prompt_payload, build_assessment_requests


def test_assessment_prompt_states_cross_field_verdict_contract() -> None:
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

    payload = json.loads(assessment_prompt_payload(request))
    contract = payload["rules"]["output_contract"]

    assert "at least one allowed category" in contract["pain"]
    assert "categories must be empty" in contract["not_pain_or_abstain"]
    assert "problem_statement must be empty" in contract["not_pain_or_abstain"]
