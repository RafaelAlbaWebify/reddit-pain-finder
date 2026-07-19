from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from painfinder.domain import PainSignal, SourceItem


STOP_WORDS = {
    "about",
    "after",
    "again",
    "automatically",
    "before",
    "client",
    "could",
    "every",
    "from",
    "have",
    "into",
    "month",
    "need",
    "really",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "tool",
    "using",
    "what",
    "when",
    "with",
    "would",
}


@dataclass(frozen=True)
class OpportunityCluster:
    key: str
    label: str
    source_ids: tuple[str, ...]
    evidence_count: int
    independent_communities: int
    average_confidence: float
    score: float
    categories: tuple[str, ...]
    sample_excerpts: tuple[str, ...]


def build_opportunity_clusters(
    items: list[SourceItem],
    signals: list[PainSignal],
) -> list[OpportunityCluster]:
    items_by_id = {item.external_id: item for item in items}
    grouped: dict[str, list[PainSignal]] = defaultdict(list)

    for signal in signals:
        item = items_by_id.get(signal.source_external_id)
        if item is None:
            continue
        key = _cluster_key(item, signal)
        grouped[key].append(signal)

    clusters = [
        _build_cluster(key, group, items_by_id)
        for key, group in grouped.items()
    ]
    return sorted(clusters, key=lambda cluster: (-cluster.score, cluster.label))


def _cluster_key(item: SourceItem, signal: PainSignal) -> str:
    tokens = _meaningful_tokens(f"{item.title} {item.body}")
    topic = "-".join(tokens[:3]) if tokens else "general"
    return f"{signal.category.value}:{topic}"


def _build_cluster(
    key: str,
    signals: list[PainSignal],
    items_by_id: dict[str, SourceItem],
) -> OpportunityCluster:
    source_ids = tuple(sorted({signal.source_external_id for signal in signals}))
    communities = {
        items_by_id[source_id].subreddit
        for source_id in source_ids
        if items_by_id[source_id].subreddit
    }
    average_confidence = sum(signal.confidence for signal in signals) / len(signals)
    category_counts = Counter(signal.category.value for signal in signals)
    categories = tuple(category for category, _ in category_counts.most_common())
    evidence_count = len(source_ids)
    independent_communities = len(communities)

    score = min(
        100.0,
        25.0
        + evidence_count * 12.0
        + independent_communities * 10.0
        + average_confidence * 35.0,
    )

    sample_excerpts = tuple(
        signal.excerpt[:300]
        for signal in sorted(signals, key=lambda value: -value.confidence)[:3]
    )

    topic = key.split(":", maxsplit=1)[1].replace("-", " ")
    label = f"{categories[0].replace('_', ' ').title()}: {topic.title()}"

    return OpportunityCluster(
        key=key,
        label=label,
        source_ids=source_ids,
        evidence_count=evidence_count,
        independent_communities=independent_communities,
        average_confidence=round(average_confidence, 2),
        score=round(score, 1),
        categories=categories,
        sample_excerpts=sample_excerpts,
    )


def _meaningful_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9-]{3,}", text.lower())
    counts = Counter(token for token in tokens if token not in STOP_WORDS)
    return [token for token, _ in counts.most_common(6)]
