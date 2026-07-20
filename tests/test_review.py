from __future__ import annotations

from pathlib import Path

import pytest

from painfinder.opportunities import OpportunityCluster
from painfinder.review import AnalystReviewService, ReviewStatus
from painfinder.storage import SQLiteResearchRepository


def _cluster(
    key: str,
    source_ids: tuple[str, ...],
    *,
    category: str,
    confidence: float,
) -> OpportunityCluster:
    return OpportunityCluster(
        key=key,
        label=key.replace("-", " ").title(),
        source_ids=source_ids,
        evidence_count=len(source_ids),
        independent_communities=1,
        average_confidence=confidence,
        score=60.0 + len(source_ids),
        categories=(category,),
        sample_excerpts=(f"Evidence for {key}",),
    )


def _service(tmp_path: Path) -> tuple[SQLiteResearchRepository, AnalystReviewService, str]:
    repository = SQLiteResearchRepository(tmp_path / "research.db")
    repository.initialize()
    run = repository.create_run("Review")
    repository.save_clusters(
        run.run_id,
        [
            _cluster(
                "invoice-workflow",
                ("one", "two", "three"),
                category="manual_work",
                confidence=0.8,
            ),
            _cluster(
                "invoice-errors",
                ("four",),
                category="reliability",
                confidence=0.6,
            ),
        ],
    )
    return repository, AnalystReviewService(repository), run.run_id


def test_accept_reject_and_annotate_are_auditable(tmp_path: Path) -> None:
    repository, service, run_id = _service(tmp_path)

    service.set_status(run_id, "invoice-workflow", ReviewStatus.ACCEPTED)
    service.annotate(run_id, "invoice-workflow", "buyer", "Bookkeeping agency")
    service.set_status(run_id, "invoice-errors", ReviewStatus.REJECTED)

    reviewed = service.reviewed_clusters(run_id)
    assert reviewed["invoice-workflow"].status is ReviewStatus.ACCEPTED
    assert reviewed["invoice-workflow"].annotations == {
        "buyer": "Bookkeeping agency"
    }
    assert reviewed["invoice-errors"].status is ReviewStatus.REJECTED

    decisions = repository.list_decisions(run_id)
    assert [decision.action for decision in decisions] == [
        "accept",
        "annotate",
        "reject",
    ]
    assert decisions[0].previous_value == "unreviewed"
    assert decisions[0].new_value == "accepted"


def test_merge_preserves_all_source_evidence(tmp_path: Path) -> None:
    _, service, run_id = _service(tmp_path)

    service.merge(run_id, "invoice-workflow", "invoice-errors")

    reviewed = service.reviewed_clusters(run_id)
    assert set(reviewed) == {"invoice-workflow"}
    merged = reviewed["invoice-workflow"]
    assert set(merged.cluster.source_ids) == {"one", "two", "three", "four"}
    assert set(merged.cluster.categories) == {"manual_work", "reliability"}
    assert set(merged.derived_from) == {"invoice-workflow", "invoice-errors"}
    assert merged.score_recalculation_required is True


def test_split_preserves_original_and_new_source_links(tmp_path: Path) -> None:
    _, service, run_id = _service(tmp_path)

    service.split(
        run_id,
        "invoice-workflow",
        "invoice-onboarding",
        ["two", "three"],
        label="Invoice onboarding",
    )

    reviewed = service.reviewed_clusters(run_id)
    original = reviewed["invoice-workflow"]
    split = reviewed["invoice-onboarding"]
    assert original.cluster.source_ids == ("one",)
    assert split.cluster.source_ids == ("two", "three")
    assert split.derived_from == ("invoice-workflow",)
    assert original.score_recalculation_required is True
    assert split.score_recalculation_required is True


def test_invalid_review_actions_fail_without_writing_decisions(tmp_path: Path) -> None:
    repository, service, run_id = _service(tmp_path)

    with pytest.raises(KeyError, match="Unknown cluster"):
        service.annotate(run_id, "missing", "buyer", "Agency")
    with pytest.raises(ValueError, match="cannot be merged into itself"):
        service.merge(run_id, "invoice-workflow", "invoice-workflow")
    with pytest.raises(ValueError, match="must belong"):
        service.split(
            run_id,
            "invoice-workflow",
            "new-cluster",
            ["missing-source"],
            label="New cluster",
        )
    with pytest.raises(ValueError, match="leave evidence"):
        service.split(
            run_id,
            "invoice-errors",
            "all-evidence",
            ["four"],
            label="All evidence",
        )

    assert repository.list_decisions(run_id) == []


def test_corrupt_or_unknown_decisions_fail_loudly(tmp_path: Path) -> None:
    repository, service, run_id = _service(tmp_path)
    repository.record_decision(
        run_id,
        "invoice-workflow",
        "unsupported-action",
        new_value="{}",
    )

    with pytest.raises(RuntimeError, match="unsupported action"):
        service.reviewed_clusters(run_id)
