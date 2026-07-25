import pytest
from pydantic import ValidationError

from painfinder.candidate_detection import (
    LegacyRuleCandidateGenerator,
    generate_candidate_signals,
    group_candidate_signals,
)
from painfinder.domain import (
    CandidateSignal,
    EvidenceField,
    EvidenceSpan,
    SignalType,
    SourceItem,
    SourceType,
)


def _item(external_id: str, *, title: str = "", body: str) -> SourceItem:
    return SourceItem(
        external_id=external_id,
        source_type=SourceType.POST,
        title=title,
        body=body,
        subreddit="smallbusiness",
        canonical_url=f"https://reddit.com/{external_id}",
    )


def test_evidence_span_requires_offsets_to_match_text() -> None:
    with pytest.raises(ValidationError):
        EvidenceSpan(
            field=EvidenceField.BODY,
            start=2,
            end=8,
            text="wrong",
        )


def test_candidate_signal_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        CandidateSignal(
            source_external_id="item-1",
            signal_type=SignalType.UNMET_OUTCOME,
            detector_id="test",
            detector_version="1",
            strength=0.5,
            evidence_spans=(),
            reason="test",
        )


def test_modular_generators_emit_exact_evidence_spans() -> None:
    item = _item(
        "item-1",
        title="Any recommendations?",
        body="I am struggling to track customer requests and do it manually every week.",
    )

    signals = generate_candidate_signals([item])

    assert {
        SignalType.RECOMMENDATION_REQUEST,
        SignalType.UNMET_OUTCOME,
        SignalType.MANUAL_WORK,
    } <= {signal.signal_type for signal in signals}

    for signal in signals:
        for span in signal.evidence_spans:
            source = item.title if span.field is EvidenceField.TITLE else item.body
            assert source[span.start : span.end] == span.text


def test_failure_and_support_language_can_coexist() -> None:
    item = _item(
        "item-2",
        body=(
            "Support never responded, sent us between departments, "
            "and then closed our account."
        ),
    )

    signals = generate_candidate_signals([item])
    signal_types = {signal.signal_type for signal in signals}

    assert SignalType.POOR_SUPPORT in signal_types
    assert SignalType.FAILURE_NARRATIVE in signal_types


def test_legacy_rules_are_exposed_without_changing_final_detector() -> None:
    item = _item(
        "item-3",
        body="Currently we use a spreadsheet because the tool keeps failing.",
    )

    signals = LegacyRuleCandidateGenerator().generate(item)

    assert signals
    assert {signal.detector_id for signal in signals} == {"legacy-pain-rules"}
    assert any(
        signal.metadata.get("pain_category") == "workaround"
        for signal in signals
    )


def test_candidate_groups_are_sorted_by_strength() -> None:
    items = [
        _item("item-4", body="Any advice? I am not sure how to price this."),
        _item("item-5", body="The service stopped working."),
    ]

    grouped = group_candidate_signals(generate_candidate_signals(items))

    assert set(grouped) == {"item-4", "item-5"}
    assert all(
        list(values) == sorted(values, key=lambda value: -value.strength)
        for values in grouped.values()
    )


def test_generic_neutral_text_can_abstain() -> None:
    item = _item(
        "item-6",
        body="Thanks for sharing the article. I enjoyed reading it.",
    )

    assert generate_candidate_signals([item]) == []
