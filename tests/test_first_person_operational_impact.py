import pytest

from painfinder.candidate_detection import generate_candidate_signals
from painfinder.domain import SignalType, SourceItem, SourceType


def _item(external_id: str, body: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.COMMENT,
        title="",
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


@pytest.mark.parametrize(
    ("external_id", "body"),
    (
        (
            "time-loss",
            "They requested another revision and I spent a ton of time on this project.",
        ),
        (
            "repeat-work",
            "We had calls bouncing around and customers having to repeat themselves.",
        ),
        (
            "sales-stall",
            "I haven't closed a deal and I am still below quota for the year.",
        ),
        (
            "failed-appeal",
            "I appealed the decision, but the appeals are pointless and my account was flagged.",
        ),
        (
            "capacity-decline",
            "Our development capacity seems lower than it was in prior years.",
        ),
    ),
)
def test_first_person_operational_impact_is_candidate(
    external_id: str,
    body: str,
) -> None:
    signals = generate_candidate_signals([_item(external_id, body)])

    assert any(
        signal.detector_id == "legacy-pain-rules"
        and signal.signal_type is SignalType.FAILURE_NARRATIVE
        and signal.reason == "first-person operational failure with concrete impact"
        for signal in signals
    )


@pytest.mark.parametrize(
    "body",
    (
        "You should check availability before booking and ask the client politely.",
        "Networking is how you access the hidden job market.",
        "I think the risk of being laid off is a bit higher, isn't it?",
        "Who are your target customers and how many did you interview?",
        "Take the severance and immediately apply for unemployment.",
        "Very jealous you got severance; a PIP usually does not qualify.",
        "Three product photographs are fine if they show different use cases.",
        "We published a free interview-practice tool and want feedback.",
        "The client would be within their rights to decline the request.",
    ),
)
def test_generic_advice_and_reviewed_false_positives_remain_negative(body: str) -> None:
    signals = generate_candidate_signals([_item("negative", body)])

    assert not any(
        signal.reason == "first-person operational failure with concrete impact"
        for signal in signals
    )
