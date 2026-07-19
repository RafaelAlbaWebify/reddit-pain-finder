import pytest

from painfinder.domain import ResearchRun
from painfinder.live import LiveCollectionNotEnabled, LiveRedditCollector


def test_live_collection_is_disabled_by_default() -> None:
    with pytest.raises(LiveCollectionNotEnabled, match="disabled"):
        LiveRedditCollector().collect(ResearchRun(name="safe-default"))
