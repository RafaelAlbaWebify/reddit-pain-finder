from itertools import combinations
from pathlib import Path

from painfinder.benchmark import load_benchmark
from painfinder.domain import PainSignal
from painfinder.opportunities import build_opportunity_clusters


def _oracle_pair_metrics(corpus: Path) -> tuple[float, float]:
    cases = load_benchmark(corpus)
    items = [case.item for case in cases]
    positive_cases = [
        case
        for case in cases
        if case.expected_pain
        and case.expected_cluster is not None
        and case.expected_categories
    ]
    signals = [
        PainSignal(
            source_external_id=case.item.external_id,
            excerpt=(case.item.title or case.item.body)[:300],
            category=case.expected_categories[0],
            confidence=1.0,
            reasons=["oracle-positive-clustering-regression"],
        )
        for case in positive_cases
    ]

    clusters = build_opportunity_clusters(items, signals)
    predicted_key = {
        source_id: cluster.key
        for cluster in clusters
        for source_id in cluster.source_ids
    }
    expected_cluster = {
        case.item.external_id: case.expected_cluster
        for case in positive_cases
    }
    ids = sorted(expected_cluster)

    expected_pairs = {
        (left, right)
        for left, right in combinations(ids, 2)
        if expected_cluster[left] == expected_cluster[right]
    }
    predicted_pairs = {
        (left, right)
        for left, right in combinations(ids, 2)
        if predicted_key.get(left) is not None
        and predicted_key.get(left) == predicted_key.get(right)
    }
    matched = expected_pairs & predicted_pairs
    precision = len(matched) / len(predicted_pairs) if predicted_pairs else 0.0
    recall = len(matched) / len(expected_pairs) if expected_pairs else 0.0
    return precision, recall


def test_semantic_clustering_recovers_original_reviewed_pairs() -> None:
    precision, recall = _oracle_pair_metrics(
        Path("benchmarks/reddit-pilot-gold-v1.jsonl")
    )

    assert precision == 1.0
    assert recall == 1.0


def test_semantic_clustering_recovers_unseen_reviewed_pairs() -> None:
    precision, recall = _oracle_pair_metrics(
        Path("benchmarks/reddit-unseen-heldout-v1.jsonl")
    )

    assert precision == 1.0
    assert recall == 1.0
