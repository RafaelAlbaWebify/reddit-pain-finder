from pathlib import Path

from typer.testing import CliRunner

from painfinder.cli import app

FIXTURE = Path(__file__).parent / "fixtures" / "reddit_thread.html"


def test_demo_command_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "cli-report.html"
    result = CliRunner().invoke(
        app,
        ["demo", "--input", str(FIXTURE), "--output", str(output)],
    )
    assert result.exit_code == 0
    assert "PASS:" in result.stdout
    assert output.exists()
