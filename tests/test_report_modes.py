from pathlib import Path

import pytest

from painfinder.report import write_html_report


def test_live_report_is_not_labeled_as_fixture(tmp_path: Path) -> None:
    output = tmp_path / "live.html"
    write_html_report(
        output,
        [],
        [],
        source_kind="live",
        stop_reason="blocked",
    )
    content = output.read_text(encoding="utf-8")
    assert "Live Collection Evidence Report" in content
    assert "Stop reason:</strong> blocked" in content
    assert "Fixture Evidence Report" not in content


def test_report_rejects_unknown_source_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source_kind"):
        write_html_report(
            tmp_path / "bad.html",
            [],
            [],
            source_kind="unknown",
        )
