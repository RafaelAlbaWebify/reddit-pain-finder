from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import SourceItem, SourceType
from painfinder.opportunities import OpportunityCluster
from painfinder.storage import SQLiteResearchRepository


def _seed_database(database: Path) -> tuple[str, str]:
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    run = repository.create_run("Review CLI")
    item = SourceItem(
        external_id="one",
        source_type=SourceType.POST,
        title="Invoice workflow",
        body="Manual invoice reconciliation takes hours.",
        subreddit="smallbusiness",
        canonical_url="https://example.com/one",
    )
    cluster = OpportunityCluster(
        key="invoice-workflow",
        label="Invoice Workflow",
        source_ids=("one",),
        evidence_count=1,
        independent_communities=1,
        average_confidence=0.8,
        score=70.0,
        categories=("manual_work",),
        sample_excerpts=("Manual invoice reconciliation takes hours.",),
    )
    repository.save_source_items(run.run_id, [item])
    repository.save_clusters(run.run_id, [cluster])
    return run.run_id, cluster.key


def test_review_status_annotation_and_report(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    run_id, cluster_key = _seed_database(database)
    runner = CliRunner()

    status = runner.invoke(
        app,
        [
            "review",
            "status",
            "--run-id",
            run_id,
            "--cluster-key",
            cluster_key,
            "--status",
            "accepted",
            "--database",
            str(database),
        ],
    )
    annotation = runner.invoke(
        app,
        [
            "review",
            "annotate",
            "--run-id",
            run_id,
            "--cluster-key",
            cluster_key,
            "--field",
            "buyer",
            "--value",
            "Bookkeeping agency",
            "--database",
            str(database),
        ],
    )
    output = tmp_path / "reviewed.html"
    report = runner.invoke(
        app,
        [
            "review",
            "report",
            "--run-id",
            run_id,
            "--database",
            str(database),
            "--output",
            str(output),
        ],
    )

    assert status.exit_code == 0
    assert "recorded accept decision" in status.stdout
    assert annotation.exit_code == 0
    assert "recorded annotation decision" in annotation.stdout
    assert report.exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "Reviewed Opportunity Report" in content
    assert "accepted" in content
    assert "Bookkeeping agency" in content
    assert "https://example.com/one" in content


def test_review_unknown_cluster_returns_concise_error(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    run_id, _ = _seed_database(database)

    result = CliRunner().invoke(
        app,
        [
            "review",
            "status",
            "--run-id",
            run_id,
            "--cluster-key",
            "missing",
            "--status",
            "accepted",
            "--database",
            str(database),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Unknown cluster: missing" in result.stdout
