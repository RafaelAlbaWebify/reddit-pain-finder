import sys
from pathlib import Path
from types import SimpleNamespace

from painfinder import live_acceptance_cli
from painfinder.domain import SourceItem, SourceType
from painfinder.live_acceptance import (
    evaluate_live_acceptance,
    write_live_acceptance_summary,
)


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


def test_write_live_acceptance_summary(tmp_path: Path) -> None:
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
    output = tmp_path / "acceptance-summary.json"
    write_live_acceptance_summary(summary, output)
    assert '"passed": true' in output.read_text(encoding="utf-8")


def test_live_acceptance_cli_rejects_empty_subreddits(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "argv", ["painfinder-live-acceptance", "--subreddits", ","])
    assert live_acceptance_cli.main() == 2


def test_live_acceptance_cli_writes_operational_artifacts(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    artifacts = tmp_path / "acceptance"

    class FakeCollector:
        def __init__(self, *, artifacts_dir: Path) -> None:
            assert artifacts_dir == artifacts

        def collect(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(items=[_item()], evidence=[], stop_reason=None)

    def write_report(path: Path, **_kwargs: object) -> None:
        path.write_text("<html>opportunities</html>", encoding="utf-8")

    monkeypatch.setattr(live_acceptance_cli, "PlaywrightRedditCollector", FakeCollector)
    monkeypatch.setattr(live_acceptance_cli, "detect_pain_signals", lambda _items: [])
    monkeypatch.setattr(live_acceptance_cli, "build_opportunity_clusters", lambda *_args: [])
    monkeypatch.setattr(live_acceptance_cli, "write_opportunity_report", write_report)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "painfinder-live-acceptance",
            "--subreddits",
            "smallbusiness",
            "--artifacts-dir",
            str(artifacts),
        ],
    )

    assert live_acceptance_cli.main() == 0
    assert (artifacts / "opportunities.html").exists()
    assert (artifacts / "source-items.jsonl").exists()
    assert (artifacts / "acceptance-summary.json").exists()
