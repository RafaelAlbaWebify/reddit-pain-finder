from pathlib import Path

import pytest
from typer.testing import CliRunner

from painfinder.analysis import detect_pain_signals
from painfinder.cli import app
from painfinder.domain import PainCategory, PainSignal, SourceItem, SourceType
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


def test_discover_command_writes_traceable_report(tmp_path: Path) -> None:
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
    assert "unique source item(s)" in report
    assert "https://www.reddit.com/" in report


def test_csv_import_trims_values(tmp_path: Path) -> None:
    path = tmp_path / "evidence.csv"
    path.write_text(
        "external_id,body,canonical_url,source_type,title,subreddit\n"
        '  post-1  ,"  Manual invoice work  ",'
        "https://example.com/source,post,  Invoice workflow  ,  accounting  \n",
        encoding="utf-8",
    )

    items = import_source_items(path)

    assert len(items) == 1
    assert items[0].external_id == "post-1"
    assert items[0].body == "Manual invoice work"
    assert items[0].title == "Invoice workflow"
    assert items[0].subreddit == "accounting"


def test_empty_inputs_return_no_items(tmp_path: Path) -> None:
    jsonl = tmp_path / "empty.jsonl"
    csv_path = tmp_path / "empty.csv"
    jsonl.write_text("\n", encoding="utf-8")
    csv_path.write_text(
        "external_id,body,canonical_url\n",
        encoding="utf-8",
    )

    assert import_source_items(jsonl) == []
    assert import_source_items(csv_path) == []


def test_missing_csv_headers_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("external_id,body\npost-1,pain\n", encoding="utf-8")

    with pytest.raises(ImportFormatError, match="canonical_url"):
        import_source_items(path)


@pytest.mark.parametrize("payload", ["[]", '"text"', "42"])
def test_jsonl_record_must_be_an_object(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(payload + "\n", encoding="utf-8")

    with pytest.raises(ImportFormatError, match="expected a JSON object"):
        import_source_items(path)


def test_same_topic_across_categories_forms_one_cluster() -> None:
    items = [
        SourceItem(
            external_id="one",
            source_type=SourceType.POST,
            title="Invoice reconciliation workflow",
            body="Invoice reconciliation workflow requires manual spreadsheet copying.",
            canonical_url="https://example.com/one",
        ),
        SourceItem(
            external_id="two",
            source_type=SourceType.POST,
            title="Invoice reconciliation workflow",
            body="Invoice reconciliation workflow needs a missing automation capability.",
            canonical_url="https://example.com/two",
        ),
    ]
    signals = [
        PainSignal(
            source_external_id="one",
            excerpt="manual spreadsheet copying",
            category=PainCategory.MANUAL_WORK,
            confidence=0.8,
            reasons=["manual"],
        ),
        PainSignal(
            source_external_id="two",
            excerpt="missing automation capability",
            category=PainCategory.EXPLICIT_DEMAND,
            confidence=0.7,
            reasons=["demand"],
        ),
    ]

    clusters = build_opportunity_clusters(items, signals)

    assert len(clusters) == 1
    assert clusters[0].evidence_count == 2
    assert set(clusters[0].categories) == {"manual_work", "explicit_demand"}


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


def test_discover_command_returns_concise_import_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    output = tmp_path / "report.html"
    path.write_text("[]\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["discover", "--input", str(path), "--output", str(output)],
    )

    assert result.exit_code == 2
    assert "ERROR:" in result.stdout
    assert "expected a JSON object" in result.stdout
    assert not output.exists()
