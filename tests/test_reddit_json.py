from painfinder.browser_models import PageState
from painfinder.reddit_json import (
    detect_reddit_response_state,
    extract_reddit_listing_json,
    extract_reddit_thread_json,
)


def test_detect_reddit_response_state_uses_status_and_explicit_markers() -> None:
    assert detect_reddit_response_state(status=403, body="") is PageState.BLOCKED
    assert detect_reddit_response_state(status=429, body="") is PageState.RATE_LIMITED
    assert (
        detect_reddit_response_state(status=200, body="Verify you are human")
        is PageState.CAPTCHA
    )
    assert detect_reddit_response_state(status=200, body='{"kind":"Listing"}') is PageState.NORMAL


def test_extract_reddit_listing_json_deduplicates_threads() -> None:
    payload = {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "title": "Manual paperwork",
                        "permalink": "/r/smallbusiness/comments/abc/manual_paperwork/",
                        "subreddit": "smallbusiness",
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "title": "Manual paperwork duplicate",
                        "permalink": "/r/smallbusiness/comments/abc/manual_paperwork/",
                        "subreddit": "smallbusiness",
                    },
                },
                {"kind": "t3", "data": {"title": "Missing URL"}},
            ]
        },
    }

    candidates = extract_reddit_listing_json(payload)

    assert len(candidates) == 1
    assert candidates[0].title == "Manual paperwork"
    assert str(candidates[0].url).startswith(
        "https://www.reddit.com/r/smallbusiness/comments/abc/"
    )


def test_extract_reddit_thread_json_collects_post_and_bounded_comments() -> None:
    payload = [
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "name": "t3_abc",
                            "title": "Paperwork takes forever",
                            "selftext": "We validate every document manually.",
                            "subreddit": "smallbusiness",
                            "permalink": "/r/smallbusiness/comments/abc/paperwork/",
                        },
                    }
                ]
            },
        },
        {
            "kind": "Listing",
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "name": "t1_one",
                            "body": "We built a spreadsheet workaround.",
                            "subreddit": "smallbusiness",
                            "permalink": (
                                "/r/smallbusiness/comments/abc/paperwork/one/"
                            ),
                            "replies": {
                                "kind": "Listing",
                                "data": {
                                    "children": [
                                        {
                                            "kind": "t1",
                                            "data": {
                                                "name": "t1_nested",
                                                "body": "Nested useful reply",
                                                "permalink": (
                                                    "/r/smallbusiness/comments/abc/"
                                                    "paperwork/nested/"
                                                ),
                                            },
                                        }
                                    ]
                                },
                            },
                        },
                    },
                    {
                        "kind": "t1",
                        "data": {
                            "name": "t1_two",
                            "body": "This should be excluded by the limit.",
                        },
                    },
                ]
            },
        },
    ]

    items = extract_reddit_thread_json(
        payload,
        page_url="https://www.reddit.com/r/smallbusiness/comments/abc/paperwork/",
        max_comments=2,
    )

    assert [item.external_id for item in items] == [
        "t3_abc",
        "t1_one",
        "t1_nested",
    ]
    assert items[0].title == "Paperwork takes forever"
    assert items[1].body == "We built a spreadsheet workaround."


def test_extract_reddit_thread_json_returns_empty_for_invalid_payload() -> None:
    assert (
        extract_reddit_thread_json(
            {},
            page_url="https://www.reddit.com/r/test/comments/missing/thread/",
            max_comments=10,
        )
        == []
    )
