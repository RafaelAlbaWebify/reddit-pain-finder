from pathlib import Path

from painfinder.analysis import detect_pain_signals
from painfinder.domain import PainCategory, SourceType
from painfinder.reddit_fixture import extract_thread_fixture
from painfinder.report import write_html_report

FIXTURE = Path(__file__).parent / "fixtures" / "reddit_thread.html"


def test_fixture_extraction_preserves_post_and_nonempty_comments() -> None:
    items = extract_thread_fixture(FIXTURE)
    assert len(items) == 3
    assert items[0].source_type == SourceType.POST
    assert items[0].subreddit == "smallbusiness"
    assert all(str(item.canonical_url).startswith("https://www.reddit.com/") for item in items)


def test_detector_finds_actionable_pain_but_not_unrelated_comment() -> None:
    items = extract_thread_fixture(FIXTURE)
    signals = detect_pain_signals(items)
    assert {signal.source_external_id for signal in signals} == {"t3_demo1", "t1_comment1"}
    assert any(signal.category == PainCategory.EXPLICIT_DEMAND for signal in signals)


def test_fixture_to_html_report(tmp_path: Path) -> None:
    items = extract_thread_fixture(FIXTURE)
    signals = detect_pain_signals(items)
    output = tmp_path / "report.html"
    write_html_report(output, items, signals)
    report = output.read_text(encoding="utf-8")
    assert "local test fixture" in report
    assert "Candidate pain signals: 2" in report
    assert "https://www.reddit.com/" in report
