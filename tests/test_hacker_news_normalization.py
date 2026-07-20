from __future__ import annotations

from typing import Any

from painfinder.domain import ResearchRun
from painfinder.hacker_news import API_BASE, HackerNewsCollector


class FakeTransport:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.calls.append(url)
        return self.responses[url]


def _policy() -> ResearchRun:
    return ResearchRun(
        name="hn-normalization",
        max_pages=10,
        max_threads=3,
        max_comments_per_thread=1,
        min_delay_seconds=0.5,
        max_runtime_seconds=900,
        live_access_enabled=True,
        concurrency=1,
    )


def test_boolean_ids_and_non_story_feed_items_are_ignored() -> None:
    feed = f"{API_BASE}/topstories.json"
    job = f"{API_BASE}/item/1.json"
    story = f"{API_BASE}/item/2.json"
    transport = FakeTransport(
        {
            feed: [True, 1, 2],
            job: {
                "id": 1,
                "type": "job",
                "title": "Hiring an engineer",
            },
            story: {
                "id": 2,
                "type": "story",
                "title": "Ask HN: Manual invoice workflow",
                "text": "We manually copy invoice totals every month.",
                "kids": [],
            },
        }
    )

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
    ).collect(policy=_policy(), feed="topstories")

    assert [item.external_id for item in result.items] == ["hn-story-2"]
    assert f"{API_BASE}/item/True.json" not in transport.calls


def test_only_comment_items_count_toward_comment_limit() -> None:
    feed = f"{API_BASE}/askstories.json"
    story = f"{API_BASE}/item/1.json"
    wrong_type = f"{API_BASE}/item/11.json"
    comment = f"{API_BASE}/item/12.json"
    transport = FakeTransport(
        {
            feed: [1],
            story: {
                "id": 1,
                "type": "story",
                "title": "Ask HN: Invoice workflow",
                "kids": [11, 12],
            },
            wrong_type: {
                "id": 11,
                "type": "story",
                "title": "Not a comment",
            },
            comment: {
                "id": 12,
                "type": "comment",
                "text": "Currently we use a spreadsheet workaround.",
            },
        }
    )

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
    ).collect(policy=_policy(), feed="askstories")

    assert [item.external_id for item in result.items] == [
        "hn-story-1",
        "hn-comment-12",
    ]
    assert comment in transport.calls
