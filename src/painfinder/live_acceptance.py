from __future__ import annotations

import json
from pathlib import Path

from painfinder.browser_models import BrowserEvidence
from painfinder.domain import SourceItem
from pydantic import BaseModel


OBSTRUCTION_REASONS = {
    "blocked",
    "captcha",
    "login_wall",
    "rate_limited",
    "selector_mismatch",
}


class LiveAcceptanceSummary(BaseModel):
    passed: bool
    stop_reason: str
    items_collected: int
    pain_signals: int
    opportunity_clusters: int
    obstruction: str | None
    report_path: str
    items_path: str
    evidence: tuple[BrowserEvidence, ...]


def evaluate_live_acceptance(
    *,
    stop_reason: str | None,
    items: list[SourceItem],
    pain_signals: int,
    opportunity_clusters: int,
    report_path: Path,
    items_path: Path,
    evidence: list[BrowserEvidence],
) -> LiveAcceptanceSummary:
    normalized = stop_reason or "completed"
    obstruction = normalized if normalized in OBSTRUCTION_REASONS else None
    passed = obstruction is None and bool(items) and report_path.exists()
    return LiveAcceptanceSummary(
        passed=passed,
        stop_reason=normalized,
        items_collected=len(items),
        pain_signals=pain_signals,
        opportunity_clusters=opportunity_clusters,
        obstruction=obstruction,
        report_path=str(report_path),
        items_path=str(items_path),
        evidence=tuple(evidence),
    )


def write_live_acceptance_summary(summary: LiveAcceptanceSummary, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
