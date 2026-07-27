from __future__ import annotations

from pathlib import Path

import pytest

from painfinder.benchmark import BenchmarkCase
from painfinder.calibration_runner import CalibrationMetrics, CalibrationRecord
from painfinder.domain import SourceItem, SourceType
from painfinder.forced_replay_cli import ForcedReplayError, force_replay_selected
from painfinder.pain_policy import FinalPolicyDecision


def _case(external_id: str, expected_pain: bool) -> BenchmarkCase:
    return BenchmarkCase(
        item=SourceItem(
            external_id=external_id,
            source_type=SourceType.POST,
            title="Test",
            body="Test body",
            subreddit="smallbusiness",
            canonical_url=f"https://reddit.com/{external_id}",
        ),
        expected_pain=expected_pain,
        expected_categories=(),
        expected_cluster=None,
    )


def _record(external_id: str, candidate_count: int) -> CalibrationRecord:
    return CalibrationRecord(
        source_external_id=external_id,
        subreddit="smallbusiness",
        expected_pain=True,
        expected_categories=(),
        candidate_count=candidate_count,
        duration_ms=1,
        decision=FinalPolicyDecision.REVIEW,
    )


def _write_corpus(path: Path, cases: list[BenchmarkCase]) -> None:
    path.write_text(
        "".join(case.model_dump_json() + "\n" for case in cases),
        encoding="utf-8",
    )


def test_force_replay_appends_selected_latest_record(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    attempts = tmp_path / "attempts.jsonl"
    metrics = tmp_path / "metrics.json"
    _write_corpus(corpus, [_case("one", True), _case("two", False)])
    attempts.write_text(
        _record("one", 0).model_dump_json()
        + "\n"
        + _record("two", 0).model_dump_json()
        + "\n",
        encoding="utf-8",
    )

    calls: list[str] = []

    def fake_runner(
        corpus_path: Path,
        config_path: Path,
        *,
        attempts_output: Path,
        metrics_output: Path,
        only_id: str | None = None,
    ) -> CalibrationMetrics:
        del corpus_path, config_path, metrics_output
        assert only_id is not None
        calls.append(only_id)
        attempts_output.write_text(
            _record(only_id, 2).model_dump_json() + "\n",
            encoding="utf-8",
        )
        return CalibrationMetrics.model_construct()

    result = force_replay_selected(
        corpus,
        tmp_path / "config.json",
        attempts_output=attempts,
        metrics_output=metrics,
        external_ids=("one",),
        replay_runner=fake_runner,
    )

    lines = attempts.read_text(encoding="utf-8").splitlines()
    assert calls == ["one"]
    assert len(lines) == 3
    assert CalibrationRecord.model_validate_json(lines[-1]).candidate_count == 2
    assert result.attempted_count == 1
    assert result.resumed_count == 1
    assert metrics.exists()


def test_force_replay_rejects_unknown_ids(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    _write_corpus(corpus, [_case("one", True)])

    with pytest.raises(ForcedReplayError, match="missing"):
        force_replay_selected(
            corpus,
            tmp_path / "config.json",
            attempts_output=tmp_path / "attempts.jsonl",
            metrics_output=tmp_path / "metrics.json",
            external_ids=("missing",),
        )
