from __future__ import annotations

from pathlib import Path

from painfinder.domain import ResearchRun, SourceItem
from painfinder.playwright_collector import LiveCollectionStopped, PlaywrightRedditCollector

LiveCollectionNotEnabled = LiveCollectionStopped


class LiveRedditCollector:
    """Compatibility wrapper around the bounded Playwright collector."""

    def collect(self, policy: ResearchRun) -> list[SourceItem]:
        result = PlaywrightRedditCollector(
            artifacts_dir=Path("artifacts/live")
        ).collect(
            policy=policy,
            subreddits=["smallbusiness"],
        )
        return result.items
