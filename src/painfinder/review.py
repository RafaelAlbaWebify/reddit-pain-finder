from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from painfinder.opportunities import OpportunityCluster
from painfinder.storage import AnalystDecision, SQLiteResearchRepository


class ReviewAction(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    ANNOTATE = "annotate"
    MERGE = "merge"
    SPLIT = "split"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReviewedCluster:
    cluster: OpportunityCluster
    status: ReviewStatus = ReviewStatus.UNREVIEWED
    annotations: dict[str, str] = field(default_factory=dict)
    derived_from: tuple[str, ...] = ()


class AnalystReviewService:
    """Append decisions and derive a reviewed cluster view without mutating evidence."""

    def __init__(self, repository: SQLiteResearchRepository) -> None:
        self.repository = repository

    def set_status(
        self,
        run_id: str,
        cluster_key: str,
        status: ReviewStatus,
    ) -> AnalystDecision:
        if status is ReviewStatus.UNREVIEWED:
            raise ValueError("Use accepted or rejected as an explicit review decision")
        current = self._required_cluster(run_id, cluster_key)
        reviewed = self.reviewed_clusters(run_id)[cluster_key]
        action = (
            ReviewAction.ACCEPT
            if status is ReviewStatus.ACCEPTED
            else ReviewAction.REJECT
        )
        return self.repository.record_decision(
            run_id,
            current.key,
            action.value,
            previous_value=reviewed.status.value,
            new_value=status.value,
        )

    def annotate(
        self,
        run_id: str,
        cluster_key: str,
        field_name: str,
        value: str,
    ) -> AnalystDecision:
        self._required_cluster(run_id, cluster_key)
        clean_field = field_name.strip()
        clean_value = value.strip()
        if not clean_field or not clean_value:
            raise ValueError("Annotation field and value must not be blank")
        reviewed = self.reviewed_clusters(run_id)[cluster_key]
        previous = reviewed.annotations.get(clean_field)
        payload = json.dumps({"field": clean_field, "value": clean_value})
        return self.repository.record_decision(
            run_id,
            cluster_key,
            ReviewAction.ANNOTATE.value,
            previous_value=previous,
            new_value=payload,
        )

    def merge(
        self,
        run_id: str,
        target_key: str,
        source_key: str,
    ) -> AnalystDecision:
        if target_key == source_key:
            raise ValueError("A cluster cannot be merged into itself")
        self._required_cluster(run_id, target_key)
        self._required_cluster(run_id, source_key)
        payload = json.dumps({"source_key": source_key})
        return self.repository.record_decision(
            run_id,
            target_key,
            ReviewAction.MERGE.value,
            new_value=payload,
        )

    def split(
        self,
        run_id: str,
        cluster_key: str,
        new_key: str,
        source_ids: list[str],
        *,
        label: str,
    ) -> AnalystDecision:
        cluster = self._required_cluster(run_id, cluster_key)
        clean_new_key = new_key.strip()
        clean_label = label.strip()
        selected = tuple(sorted({value.strip() for value in source_ids if value.strip()}))
        if not clean_new_key or not clean_label:
            raise ValueError("Split key and label must not be blank")
        if clean_new_key in self.reviewed_clusters(run_id):
            raise ValueError(f"Cluster key already exists: {clean_new_key}")
        if not selected:
            raise ValueError("A split requires at least one source item")
        if not set(selected).issubset(cluster.source_ids):
            raise ValueError("Split source IDs must belong to the original cluster")
        if set(selected) == set(cluster.source_ids):
            raise ValueError("A split must leave evidence in the original cluster")
        payload = json.dumps(
            {
                "new_key": clean_new_key,
                "label": clean_label,
                "source_ids": selected,
            }
        )
        return self.repository.record_decision(
            run_id,
            cluster_key,
            ReviewAction.SPLIT.value,
            new_value=payload,
        )

    def reviewed_clusters(self, run_id: str) -> dict[str, ReviewedCluster]:
        reviewed = {
            cluster.key: ReviewedCluster(
                cluster=cluster,
                derived_from=(cluster.key,),
            )
            for cluster in self.repository.list_clusters(run_id)
        }
        for decision in self.repository.list_decisions(run_id):
            self._apply_decision(reviewed, decision)
        return reviewed

    def _apply_decision(
        self,
        reviewed: dict[str, ReviewedCluster],
        decision: AnalystDecision,
    ) -> None:
        current = reviewed.get(decision.cluster_key)
        if current is None:
            return
        if decision.action == ReviewAction.ACCEPT.value:
            reviewed[decision.cluster_key] = replace(
                current,
                status=ReviewStatus.ACCEPTED,
            )
            return
        if decision.action == ReviewAction.REJECT.value:
            reviewed[decision.cluster_key] = replace(
                current,
                status=ReviewStatus.REJECTED,
            )
            return
        if decision.action == ReviewAction.ANNOTATE.value:
            payload = _payload(decision)
            annotations = dict(current.annotations)
            annotations[str(payload["field"])] = str(payload["value"])
            reviewed[decision.cluster_key] = replace(
                current,
                annotations=annotations,
            )
            return
        if decision.action == ReviewAction.MERGE.value:
            payload = _payload(decision)
            source_key = str(payload["source_key"])
            source = reviewed.get(source_key)
            if source is None:
                return
            reviewed[decision.cluster_key] = replace(
                current,
                cluster=_merge_clusters(current.cluster, source.cluster),
                derived_from=tuple(
                    sorted(set(current.derived_from) | set(source.derived_from))
                ),
            )
            del reviewed[source_key]
            return
        if decision.action == ReviewAction.SPLIT.value:
            payload = _payload(decision)
            selected = tuple(str(value) for value in payload["source_ids"])
            remaining = tuple(
                value for value in current.cluster.source_ids if value not in selected
            )
            reviewed[decision.cluster_key] = replace(
                current,
                cluster=replace(
                    current.cluster,
                    source_ids=remaining,
                    evidence_count=len(remaining),
                ),
            )
            new_key = str(payload["new_key"])
            new_cluster = replace(
                current.cluster,
                key=new_key,
                label=str(payload["label"]),
                source_ids=selected,
                evidence_count=len(selected),
            )
            reviewed[new_key] = ReviewedCluster(
                cluster=new_cluster,
                derived_from=current.derived_from,
            )

    def _required_cluster(self, run_id: str, cluster_key: str) -> OpportunityCluster:
        clusters = self.reviewed_clusters(run_id)
        reviewed = clusters.get(cluster_key)
        if reviewed is None:
            raise KeyError(f"Unknown cluster: {cluster_key}")
        return reviewed.cluster


def _payload(decision: AnalystDecision) -> dict[str, Any]:
    if decision.new_value is None:
        raise RuntimeError(f"Decision {decision.decision_id} has no payload")
    value = json.loads(decision.new_value)
    if not isinstance(value, dict):
        raise RuntimeError(f"Decision {decision.decision_id} payload is invalid")
    return value


def _merge_clusters(
    target: OpportunityCluster,
    source: OpportunityCluster,
) -> OpportunityCluster:
    source_ids = tuple(sorted(set(target.source_ids) | set(source.source_ids)))
    categories = tuple(sorted(set(target.categories) | set(source.categories)))
    excerpts = tuple(dict.fromkeys(target.sample_excerpts + source.sample_excerpts))[:3]
    total_evidence = target.evidence_count + source.evidence_count
    average_confidence = (
        target.average_confidence * target.evidence_count
        + source.average_confidence * source.evidence_count
    ) / total_evidence
    return replace(
        target,
        source_ids=source_ids,
        evidence_count=len(source_ids),
        independent_communities=max(
            target.independent_communities,
            source.independent_communities,
        ),
        average_confidence=round(average_confidence, 2),
        score=max(target.score, source.score),
        categories=categories,
        sample_excerpts=excerpts,
    )
