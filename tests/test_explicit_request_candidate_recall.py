from __future__ import annotations

import pytest

from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import SourceItem, SourceType


def _item(external_id: str, text: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title=text,
        body="",
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


@pytest.mark.parametrize(
    "text",
    (
        "What is the best way to market our SaaS via LinkedIn?",
        "I need some guidance about this product-owner interview loop.",
        "Is anyone else reselling QuickBooks Online?",
        "Anyone recently cleared the interview loops for this role?",
        "Is it a good long-term career with high earning potential?",
        "How many are enough for a first manufacturing run?",
        "Can I change the quote after the studio price increased?",
        "Pourriez-vous me conseiller des app pour auditer mon SaaS ?",
    ),
)
def test_explicit_business_requests_generate_candidates(text: str) -> None:
    signals = generate_candidate_signals([_item("positive", text)])

    assert signals
    assert any(signal.detector_id == "legacy-pain-rules" for signal in signals)


@pytest.mark.parametrize(
    "text",
    (
        "Can I share a project update here?",
        "Anyone recently joined our company newsletter.",
        "Is anyone else online today?",
        "How many people attended the launch?",
        "This is a good long-term career overview.",
    ),
)
def test_generic_questions_do_not_generate_candidates(text: str) -> None:
    assert generate_candidate_signals([_item("negative", text)]) == []
