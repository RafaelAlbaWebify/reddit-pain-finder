from pathlib import Path

import pytest

from painfinder.domain import ResearchRun
from painfinder.playwright_collector import (
    LiveCollectionStopped,
    PlaywrightRedditCollector,
)


def test_playwright_collector_refuses_disabled_policy(tmp_path: Path) -> None:
    collector = PlaywrightRedditCollector(artifacts_dir=tmp_path)
    with pytest.raises(LiveCollectionStopped, match="disabled"):
        collector.collect(
            policy=ResearchRun(name="disabled"),
            subreddits=["smallbusiness"],
        )


def test_playwright_collector_rejects_missing_subreddits(tmp_path: Path) -> None:
    collector = PlaywrightRedditCollector(artifacts_dir=tmp_path)
    with pytest.raises(ValueError, match="seed subreddit"):
        collector.collect(
            policy=ResearchRun(name="enabled", live_access_enabled=True),
            subreddits=[],
        )
