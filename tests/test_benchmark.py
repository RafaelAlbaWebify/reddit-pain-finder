from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from painfinder.benchmark import BenchmarkFormatError, evaluate_benchmark, load_benchmark
from painfinder.cli import app

CORPUS = Path(__file__).parent / "fixtures" / "benchmark_corpus.jsonl"


def test_reviewed_corpus_evaluates_detector_and_clustering() -> None:
    cases = load_benchmark(CORPUS)
    result = evaluate_benchmark(cases)

    assert result.case_count == 4
    assert result.true_positive == 3
    assert result.true_negative == 1
    assert result.false_positive == 0
    assert result.false_negative == 0
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.category_recall == 1.0
    assert result.cluster_pair_precision == 1.0
    assert result.cluster_pair_recall == 1.0
    assert result.fragmentation_pairs == ()
    assert result.overmerge_pairs == ()


def test_benchmark_cli_writes_machine_and_human_results(tmp_path: Path) -> None:
    json_output = tmp_path / "results.json"
    html_output = tmp_path / "results.html"
    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "run",
            "--corpus",
            str(CORPUS),
            "--json-output",
            str(json_output),
            "--html-output",
            str(html_output),
        ],
    )

    assert result.exit_code == 0
    assert "precision=1.000" in result.stdout
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["metrics"]["recall"] == 1.0
    report = html_output.read_text(encoding="utf-8")
    assert "Benchmark Evaluation" in report
    assert "do not estimate market size" in report


def test_benchmark_rejects_non_boolean_expected_pain(tmp_path: Path) -> None:
    corpus = tmp_path / "bad.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "item": {
                    "external_id": "one",
                    "source_type": "post",
                    "title": "Test",
                    "body": "Test body",
                    "canonical_url": "https://example.com/one",
                },
                "expected_pain": "yes",
                "expected_categories": [],
                "expected_cluster": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkFormatError, match="expected_pain must be boolean"):
        load_benchmark(corpus)


def test_benchmark_cli_returns_concise_format_error(tmp_path: Path) -> None:
    corpus = tmp_path / "bad.jsonl"
    corpus.write_text("[]\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "run",
            "--corpus",
            str(corpus),
            "--json-output",
            str(tmp_path / "results.json"),
            "--html-output",
            str(tmp_path / "results.html"),
        ],
    )

    assert result.exit_code == 2
    assert "ERROR: Invalid benchmark case on line 1" in result.stdout
