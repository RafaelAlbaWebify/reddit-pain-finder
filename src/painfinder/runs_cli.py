from __future__ import annotations

from pathlib import Path
from typing import Annotated, Never

import typer

from painfinder.run_catalog import SQLiteRunCatalog

runs_app = typer.Typer(no_args_is_help=True)


@runs_app.command("list")
def list_runs(
    database: Annotated[Path, typer.Option()] = Path("data/research.db"),
) -> None:
    """List persisted research runs, newest first."""
    catalog = SQLiteRunCatalog(database)
    runs = catalog.list_runs()
    if not runs:
        typer.echo("No research runs found.")
        return

    typer.echo("RUN ID\tSTATUS\tCREATED\tNAME")
    for run in runs:
        typer.echo(
            f"{run.run_id}\t{run.status}\t{run.created_at.isoformat()}\t{run.name}"
        )


@runs_app.command("show")
def show_run(
    run_id: Annotated[str, typer.Option()],
    database: Annotated[Path, typer.Option()] = Path("data/research.db"),
) -> None:
    """Show persisted evidence and review counts for one run."""
    catalog = SQLiteRunCatalog(database)
    try:
        summary = catalog.get_summary(run_id)
    except KeyError as error:
        _fail(error)

    typer.echo(f"Run ID: {summary.run.run_id}")
    typer.echo(f"Name: {summary.run.name}")
    typer.echo(f"Status: {summary.run.status}")
    typer.echo(f"Created: {summary.run.created_at.isoformat()}")
    typer.echo(f"Source items: {summary.source_items}")
    typer.echo(f"Pain signals: {summary.pain_signals}")
    typer.echo(f"Clusters: {summary.clusters}")
    typer.echo(f"Decisions: {summary.decisions}")


def _fail(error: Exception) -> Never:
    message = error.args[0] if error.args else str(error)
    typer.echo(f"ERROR: {message}")
    raise typer.Exit(code=2) from error
