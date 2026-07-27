from pathlib import Path

from painfinder.domain import SourceItem, SourceType
from painfinder.live_acceptance import evaluate_live_acceptance


def _item() -> SourceItem:
    return SourceItem(
        external_id="t3_live",
        source_type=SourceType.POST,
        title="Example",
        body="We have no closed deals and are missing quota.",
        subreddit="smallbusiness",
        canonical_url="https://www.reddit.com/r/smallbusiness/comments/live/example/",
    )


def test_live_acceptance_passes_with_items_and_report(tmp_path: Path) -> None:
    report = tmp_path / "opportunities.html"
    report.write_text("<html></html>", encoding="utf-8")
    summary = evaluate_live_acceptance(
        stop_reason=None,
        items=[_item()],
        pain_signals=1,
        opportunity_clusters=1,
        report_path=report,
        items_path=tmp_path / "items.jsonl",
        evidence=[],
    )
    assert summary.passed
    assert summary.obstruction is None


def test_live_acceptance_fails_for_captcha(tmp_path: Path) -> None:
    report = tmp_path / "opportunities.html"
    report.write_text("<html></html>", encoding="utf-8")
    summary = evaluate_live_acceptance(
        stop_reason="captcha",
        items=[_item()],
        pain_signals=1,
        opportunity_clusters=1,
        report_path=report,
        items_path=tmp_path / "items.jsonl",
        evidence=[],
    )
    assert not summary.passed
    assert summary.obstruction == "captcha"


def test_live_acceptance_fails_when_collection_is_empty(tmp_path: Path) -> None:
    report = tmp_path / "opportunities.html"
    report.write_text("<html></html>", encoding="utf-8")
    summary = evaluate_live_acceptance(
        stop_reason="completed",
        items=[],
        pain_signals=0,
        opportunity_clusters=0,
        report_path=report,
        items_path=tmp_path / "items.jsonl",
        evidence=[],
    )
    assert not summary.passed
