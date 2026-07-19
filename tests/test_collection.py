import pytest

from painfinder.collection import CollectionBudget, StopReason, ensure_allowed_reddit_url
from painfinder.domain import ResearchRun


def test_budget_stops_before_exceeding_page_limit() -> None:
    budget = CollectionBudget(ResearchRun(name="bounded", max_pages=2))
    assert budget.register_page() is None
    assert budget.register_page() is None
    assert budget.register_page() == StopReason.BUDGET_EXHAUSTED
    assert budget.pages_visited == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://www.reddit.com/r/test",
        "https://example.com/reddit",
        "https://reddit.example.com/r/test",
    ],
)
def test_non_approved_navigation_is_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        ensure_allowed_reddit_url(url)


def test_approved_reddit_navigation_is_accepted() -> None:
    ensure_allowed_reddit_url("https://www.reddit.com/r/smallbusiness")
