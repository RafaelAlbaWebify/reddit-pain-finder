from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from painfinder.review import AnalystReviewService, ReviewStatus
from painfinder.review_report import write_review_report
from painfinder.storage import SQLiteResearchRepository

review_app = typer.Typer(no_args_is_help=True)


@review_app.command("status")
def set_status(
    run_id: Annotated[str, typer.Option()],
    cluster_key: Annotated[str, typer.Option()],
    status: Annotated[ReviewStatus, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path(
        "data/research.db"
    ),
) -> None:
    """Accept or reject one candidate cluster."""
    service = _service(database)
    try:
        decision = service.set_status(run_id, cluster_key, status)
    except (KeyError, ValueError) as error:
        _fail(error)
    typer.echo(f"PASS: recorded {decision.action} decision {decision.decision_id}")


@review_app.command("annotate")
def annotate(
    run_id: Annotated[str, typer.Option()],
    cluster_key: Annotated[str, typer.Option()],
    field: Annotated[str, typer.Option()],
    value: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path(
        "data/research.db"
    ),
) -> None:
    """Add or replace one analyst annotation."""
    service = _service(database)
    try:
        decision = service.annotate(run_id, cluster_key, field, value)
    except (KeyError, ValueError) as error:
        _fail(error)
    typer.echo(f"PASS: recorded annotation decision {decision.decision_id}")


@review_app.command("merge")
def merge(
    run_id: Annotated[str, typer.Option()],
    target_key: Annotated[str, typer.Option()],
    source_key: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path(
        "data/research.db"
    ),
) -> None:
    """Merge a source cluster into a target reviewed cluster."""
    service = _service(database)
    try:
        decision = service.merge(run_id, target_key, source_key)
    except (KeyError, ValueError) as error:
        _fail(error)
    typer.echo(f"PASS: recorded merge decision {decision.decision_id}")


@review_app.command("split")
def split(
    run_id: Annotated[str, typer.Option()],
    cluster_key: Annotated[str, typer.Option()],
    new_key: Annotated[str, typer.Option()],
    source_ids: Annotated[str, typer.Option()],
    label: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path(
        "data/research.db"
    ),
) -> None:
    """Split selected comma-separated evidence IDs into a reviewed cluster."""
    service = _service(database)
    selected = [value.strip() for value in source_ids.split(",") if value.strip()]
    try:
        decision = service.split(
            run_id,
            cluster_key,
            new_key,
            selected,
            label=label,
        )
    except (KeyError, ValueError) as error:
        _fail(error)
    typer.echo(f"PASS: recorded split decision {decision.decision_id}")


@review_app.command("report")
def report(
    run_id: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option(exists=True, readable=True)] = Path(
        "data/research.db"
    ),
    output: Annotated[Path, typer.Option()] = Path("output/reviewed-opportunities.html"),
) -> None:
    """Generate a reviewed report from persisted evidence and decisions."""
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    if repository.get_run(run_id) is None:
        _fail(KeyError(f"Unknown run: {run_id}"))
    service = AnalystReviewService(repository)
    write_review_report(
        output,
        items=repository.list_source_items(run_id),
        reviewed=service.reviewed_clusters(run_id),
    )
    typer.echo(f"PASS: wrote reviewed report to {output}")


def _service(database: Path) -> AnalystReviewService:
    repository = SQLiteResearchRepository(database)
    repository.initialize()
    return AnalystReviewService(repository)


def _fail(error: Exception) -> NoReturn:
    message = error.args[0] if error.args else str(error)
    typer.echo(f"ERROR: {message}")
    raise typer.Exit(code=2) from error
