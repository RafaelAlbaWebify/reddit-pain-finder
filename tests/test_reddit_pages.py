from pathlib import Path

import pytest

from painfinder.browser_models import PageState
from painfinder.reddit_pages import (
    detect_page_state,
    extract_old_reddit_listing,
    extract_old_reddit_thread,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>You've been blocked by network security</p>", PageState.BLOCKED),
        ("<p>Verify you are human with CAPTCHA</p>", PageState.CAPTCHA),
        ("<p>Too many requests</p>", PageState.RATE_LIMITED),
        ("<p>Log in to continue</p>", PageState.LOGIN_WALL),
        ("<p>normal discussion page</p>", PageState.NORMAL),
    ],
)
def test_detect_page_state(html: str, expected: PageState) -> None:
    assert detect_page_state(html) is expected


def test_extract_listing_deduplicates_and_excludes_non_threads() -> None:
    html = (FIXTURES / "old_reddit_listing.html").read_text(encoding="utf-8")
    candidates = extract_old_reddit_listing(html)
    assert [candidate.title for candidate in candidates] == [
        "Reporting pain",
        "Invoice pain",
    ]


def test_extract_thread_respects_comment_limit_and_deleted_content() -> None:
    html = (FIXTURES / "old_reddit_thread.html").read_text(encoding="utf-8")
    items = extract_old_reddit_thread(
        html,
        page_url="https://old.reddit.com/r/smallbusiness/comments/alpha/reporting/",
        max_comments=1,
    )
    assert len(items) == 2
    assert items[0].title == "Monthly reporting takes forever"
    assert items[1].external_id == "t1_one"


def test_missing_thread_container_returns_empty_collection() -> None:
    assert (
        extract_old_reddit_thread(
            "<html></html>",
            page_url="https://old.reddit.com/r/test/comments/missing/",
            max_comments=10,
        )
        == []
    )
