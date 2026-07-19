from pathlib import Path

import pytest
from typer.testing import CliRunner

from painfinder.analysis import detect_pain_signals
from painfinder.cli import app
from painfinder.importers import ImportFormatError, deduplicate_items, import_source_items
from painfinder.opportunities import build_opportunity_clusters

FIXTURE = Path(__file__).parent / "fixtures" / "imported_evidence.jsonl"


def test_import_deduplicate_detect_and_cluster() -> None:
    imported = import_source_items(FIXTURE)
    unique = deduplicate_items(imported)
    signals = detect_pain_signals(unique)
    clusters = build_opportunity_clusters(unique, signals)

    assert len(imported) == 4
    assert len(unique) == 3
    assert len(signals) == 3
    assert clusters
    assert clusters[0].score >= clusters[-1].score
    assert all(cluster.evidence_count >= 1 for cluster in clusters)


def test_discover_command_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "opportunities.html"
    result = CliRunner().invoke(
        app,
        ["discover", "--input", str(FIXTURE), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "retained 3 unique item(s)" in result.stdout
    report = output.read_text(encoding="utf-8")
    assert "Opportunity Discovery Report" in report
    assert "Scores prioritize evidence" in report


def test_unsupported_import_format_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "evidence.txt"
    path.write_text("not supported", encoding="utf-8")
    with pytest.raises(ImportFormatError, match="Supported import formats"):
        import_source_items(path)


def test_invalid_jsonl_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("{invalid}\n", encoding="utf-8")
    with pytest.raises(ImportFormatError, match="line 1"):
        import_source_items(path)
