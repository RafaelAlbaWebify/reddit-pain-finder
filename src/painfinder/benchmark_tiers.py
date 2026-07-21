from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from painfinder.benchmark import BenchmarkCase, evaluate_benchmark, load_benchmark
from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.domain import PainCategory, SourceItem


class TieredBenchmarkError(RuntimeError):
    pass


def write_tiered_benchmark_report(
    provisional_csv: Path,
    gold_corpus: Path,
    *,
    json_output: Path,
    html_output: Path,
) -> dict[str, object]:
    provisional_cases = _load_provisional_cases(provisional_csv)
    gold_cases = load_benchmark(gold_corpus)
    provisional_result = evaluate_benchmark(provisional_cases)
    gold_result = evaluate_benchmark(gold_cases)
    payload = {
        "provisional": {
            "provenance": "ai_unanimous_not_human_approved",
            "result": asdict(provisional_result),
        },
        "gold": {
            "provenance": "explicitly_human_approved",
            "result": asdict(gold_result),
        },
        "warning": (
            "Provisional metrics are exploratory and must not be presented as "
            "human-reviewed ground truth."
        ),
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(_html(payload), encoding="utf-8")
    return payload


def _load_provisional_cases(path: Path) -> list[BenchmarkCase]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames[: len(REVIEW_COLUMNS)] != REVIEW_COLUMNS:
            raise TieredBenchmarkError("Provisional review has unexpected columns")
        rows = list(reader)
    cases: list[BenchmarkCase] = []
    for line_number, row in enumerate(rows, start=2):
        try:
            expected_pain = _parse_bool(row.get("expected_pain") or "")
            categories = tuple(
                PainCategory(value.strip())
                for value in (row.get("expected_categories") or "").split(",")
                if value.strip()
            )
            cluster = (row.get("expected_cluster") or "").strip() or None
            item = SourceItem.model_validate(
                {
                    "external_id": row.get("external_id") or "",
                    "source_type": row.get("source_type") or "",
                    "title": row.get("title") or "",
                    "body": row.get("body") or "",
                    "subreddit": (row.get("community") or "").strip() or None,
                    "canonical_url": row.get("canonical_url") or "",
                }
            )
        except (ValueError, ValidationError) as error:
            raise TieredBenchmarkError(
                f"Invalid provisional review line {line_number}: {error}"
            ) from error
        cases.append(
            BenchmarkCase(
                item=item,
                expected_pain=expected_pain,
                expected_categories=categories,
                expected_cluster=cluster,
            )
        )
    return cases


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("expected_pain must be true or false")


def _html(payload: dict[str, object]) -> str:
    provisional = payload["provisional"]
    gold = payload["gold"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Tiered benchmark</title></head>
<body><h1>Tiered benchmark</h1>
<p><strong>Warning:</strong> {payload['warning']}</p>
<h2>Provisional AI consensus</h2><pre>{json.dumps(provisional, indent=2)}</pre>
<h2>Human-approved gold corpus</h2><pre>{json.dumps(gold, indent=2)}</pre>
</body></html>"""
