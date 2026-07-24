from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from painfinder.domain import PainSignal, SourceItem

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "automatically",
    "because",
    "before",
    "client",
    "could",
    "every",
    "from",
    "have",
    "into",
    "just",
    "like",
    "month",
    "more",
    "need",
    "really",
    "some",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "thing",
    "things",
    "tool",
    "using",
    "very",
    "what",
    "when",
    "with",
    "would",
    "your",
}

_TOPIC_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "dark-mode-demand",
        (
            re.compile(r"\bdark mode\b"),
            re.compile(r"\blight mode\b"),
        ),
    ),
    (
        "meta-account-recovery",
        (
            re.compile(r"\bfacebook\b.*\b(disabled|locked|verify|identity)\b"),
            re.compile(r"\bmeta\b.*\baccount\b.*\bdisabled\b"),
        ),
    ),
    (
        "cold-outreach-trust",
        (
            re.compile(r"\bcold (email|emails|outreach|sell|selling)\b"),
            re.compile(r"\bspanish\b.*\b(sell|business|relationship|trust)\b"),
            re.compile(r"\bspain\b.*\b(sell|business|relationship|trust)\b"),
        ),
    ),
    (
        "failed-startup-asset-recovery",
        (
            re.compile(r"\bfailed startup"),
            re.compile(r"\bgraveyard\b.*\bstartup"),
            re.compile(r"\b(sold for parts|core assets|acqui-hire|shut down|shutdown)\b"),
        ),
    ),
    (
        "agency-platform-scaling",
        (
            re.compile(r"\bgohighlevel\b"),
            re.compile(r"\boutgrowing\b.*\bplatform\b"),
        ),
    ),
    (
        "client-fit-and-onboarding-risk",
        (
            re.compile(r"\bprospect\b.*\b(gut|onboarding|red flag|fired|qualif)"),
            re.compile(r"\b(gut|red flag|fired my team)\b.*\b(prospect|onboarding|client)"),
        ),
    ),
    (
        "client-requirements-clarity",
        (
            re.compile(r"\b(ask|asking) questions\b"),
            re.compile(r"\bclarif(y|ied|ication)\b"),
            re.compile(r"\bvision\b.*\b(onboarding|question|assume)\b"),
            re.compile(r"\bimprove your onboarding process\b"),
            re.compile(r"\bfiguring things out with you\b"),
        ),
    ),
    (
        "client-status-visibility",
        (
            re.compile(r"\b(progress|status|update)\b.*\bclient"),
            re.compile(r"\bclient\b.*\b(progress|status|update|guess what)"),
            re.compile(r"\banswer fast\b"),
            re.compile(r"\bseen (their|the) message\b"),
            re.compile(r"\b(clients?|client) guess what('s| is|s)? happening\b"),
            re.compile(r"\bprogress is good\b"),
        ),
    ),
    (
        "scope-creep-management",
        (
            re.compile(
                r"\b(out of scope|expand the scope|scope creep|last-minute change|"
                r"ask for changes|charge for every)\b"
            ),
        ),
    ),
    (
        "cash-flow-discipline",
        (
            re.compile(r"\b(cash flow|cash-poor|overspending|budgeting)\b"),
            re.compile(r"\bpay yourself a fixed salary\b"),
        ),
    ),
)


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
        grouped[_cluster_key(item)].append(signal)

    clusters = [
        _build_cluster(key, group, items_by_id)
        for key, group in grouped.items()
    ]
    return sorted(clusters, key=lambda cluster: (-cluster.score, cluster.label))


def _cluster_key(item: SourceItem) -> str:
    text = _normalized_text(f"{item.title} {item.body}")
    semantic_topic = _semantic_topic(text)
    if semantic_topic is not None:
        return semantic_topic

    tokens = _meaningful_tokens(text)
    return "-".join(tokens[:3]) if tokens else "general"


def _semantic_topic(text: str) -> str | None:
    for topic, patterns in _TOPIC_RULES:
        if any(pattern.search(text) for pattern in patterns):
            return topic
    return None


def _normalized_text(text: str) -> str:
    lowered = text.lower().replace("’", "'")
    return " ".join(lowered.split())


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

    topic = key.replace("-", " ").title()
    category_label = ", ".join(
        category.replace("_", " ").title() for category in categories
    )
    label = f"{topic} ({category_label})"

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
