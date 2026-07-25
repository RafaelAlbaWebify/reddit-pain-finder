from pathlib import Path

from painfinder.benchmark import BenchmarkCase
from painfinder.candidate_benchmark import (
    evaluate_candidate_benchmark,
    write_candidate_benchmark_results,
)
from painfinder.domain import SourceItem, SourceType


def _case(
    external_id: str,
    body: str,
    *,
    expected_pain: bool,
) -> BenchmarkCase:
    return BenchmarkCase(
        item=SourceItem(
            external_id=external_id,
            source_type=SourceType.POST,
            title="",
            body=body,
            subreddit="smallbusiness",
            canonical_url=f"https://reddit.com/{external_id}",
        ),
        expected_pain=expected_pain,
        expected_categories=(),
        expected_cluster=None,
    )


def test_candidate_benchmark_counts_confusion_matrix() -> None:
    result = evaluate_candidate_benchmark(
        [
            _case(
                "tp",
                "I am struggling to manage customer requests.",
                expected_pain=True,
            ),
            _case(
                "fp",
                "Any recommendations?",
                expected_pain=False,
            ),
            _case(
                "tn",
                "Thanks for sharing this article.",
                expected_pain=False,
            ),
            _case(
                "fn",
                "This situation is difficult.",
                expected_pain=True,
            ),
        ]
    )

    assert result.true_positive == 1
    assert result.false_positive == 1
    assert result.true_negative == 1
    assert result.false_negative == 1
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.evidence_span_validity == 1.0


def test_candidate_benchmark_writes_json_and_html(tmp_path: Path) -> None:
    result = evaluate_candidate_benchmark(
        [
            _case(
                "one",
                "The service stopped working.",
                expected_pain=True,
            )
        ]
    )
    json_output = tmp_path / "candidate.json"
    html_output = tmp_path / "candidate.html"

    write_candidate_benchmark_results(
        result,
        json_output=json_output,
        html_output=html_output,
    )

    assert '"recall": 1.0' in json_output.read_text(encoding="utf-8")
    html_text = html_output.read_text(encoding="utf-8")
    assert "Candidate Generation Benchmark" in html_text
    assert "failure_narrative" in html_text
