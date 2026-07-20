from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest
from typer.testing import CliRunner

from painfinder.cli import app
from painfinder.domain import ResearchRun, SourceItem, SourceType
from painfinder.hacker_news import (
    API_BASE,
    HackerNewsCollectionResult,
    HackerNewsCollector,
    HackerNewsEvidence,
    _ensure_allowed_url,
)


class FakeTransport:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def _policy(
    *,
    max_pages: int = 10,
    max_threads: int = 2,
    max_comments: int = 1,
    max_runtime_seconds: int = 900,
) -> ResearchRun:
    return ResearchRun(
        name="hn-test",
        max_pages=max_pages,
        max_threads=max_threads,
        max_comments_per_thread=max_comments,
        min_delay_seconds=0.5,
        max_runtime_seconds=max_runtime_seconds,
        live_access_enabled=True,
        concurrency=1,
    )


def test_collects_bounded_stories_and_comments() -> None:
    feed = f"{API_BASE}/askstories.json"
    story_one = f"{API_BASE}/item/1.json"
    comment = f"{API_BASE}/item/11.json"
    story_two = f"{API_BASE}/item/2.json"
    transport = FakeTransport(
        {
            feed: [1, 2, 3],
            story_one: {
                "id": 1,
                "title": "Ask HN: Invoice workflow",
                "text": "We <b>manually</b> copy invoices into a spreadsheet.",
                "kids": [11, 12],
            },
            comment: {
                "id": 11,
                "text": "Currently we use a spreadsheet workaround.",
            },
            story_two: {
                "id": 2,
                "title": "Ask HN: CRM imports",
                "text": "Our CRM keeps failing during imports.",
                "kids": [],
            },
        }
    )
    delays: list[float] = []

    result = HackerNewsCollector(
        transport=transport,
        sleep=delays.append,
    ).collect(policy=_policy(), feed="askstories")

    assert result.stop_reason == "budget_exhausted"
    assert [item.external_id for item in result.items] == [
        "hn-story-1",
        "hn-comment-11",
        "hn-story-2",
    ]
    assert result.items[0].body == "We manually copy invoices into a spreadsheet."
    assert result.items[1].source_type is SourceType.COMMENT
    assert str(result.items[1].canonical_url) == (
        "https://news.ycombinator.com/item?id=11"
    )
    assert f"{API_BASE}/item/12.json" not in transport.calls
    assert delays == [0.5, 0.5, 0.5]


def test_rate_limit_stops_collection() -> None:
    feed = f"{API_BASE}/newstories.json"
    story = f"{API_BASE}/item/1.json"
    error = HTTPError(story, 429, "rate limited", hdrs=None, fp=None)
    transport = FakeTransport({feed: [1], story: error})

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
    ).collect(policy=_policy(), feed="newstories")

    assert result.items == []
    assert result.stop_reason == "rate_limited"
    assert result.evidence[-1].detail == "HTTP 429"


def test_malformed_feed_is_classified() -> None:
    feed = f"{API_BASE}/beststories.json"
    transport = FakeTransport({feed: {"not": "a list"}})

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
    ).collect(policy=_policy(), feed="beststories")

    assert result.stop_reason == "malformed_response"
    assert result.evidence[-1].status == "malformed"


def test_policy_and_host_boundaries_are_enforced() -> None:
    collector = HackerNewsCollector(
        transport=FakeTransport({}),
        sleep=lambda _: None,
    )
    disabled = _policy().model_copy(update={"live_access_enabled": False})

    with pytest.raises(ValueError, match="explicitly enabled"):
        collector.collect(policy=disabled)
    with pytest.raises(ValueError, match="Unsupported Hacker News feed"):
        collector.collect(policy=_policy(), feed="unknown")
    with pytest.raises(ValueError, match="outside approved"):
        _ensure_allowed_url("https://example.com/v0/item/1.json")
    with pytest.raises(ValueError, match="outside approved"):
        _ensure_allowed_url("http://hacker-news.firebaseio.com/v0/item/1.json")
    with pytest.raises(ValueError, match="outside approved"):
        _ensure_allowed_url(
            "https://hacker-news.firebaseio.com/v0/item/1.json?redirect=1"
        )


def test_page_budget_stops_before_fetching_story() -> None:
    feed = f"{API_BASE}/topstories.json"
    transport = FakeTransport({feed: [1]})

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
    ).collect(policy=_policy(max_pages=1), feed="topstories")

    assert result.stop_reason == "budget_exhausted"
    assert transport.calls == [feed]


def test_runtime_budget_stops_after_feed_request() -> None:
    feed = f"{API_BASE}/topstories.json"
    transport = FakeTransport({feed: [1]})
    clock_values = iter([0.0, 0.0, 31.0])

    result = HackerNewsCollector(
        transport=transport,
        sleep=lambda _: None,
        clock=lambda: next(clock_values),
    ).collect(
        policy=_policy(max_runtime_seconds=30),
        feed="topstories",
    )

    assert result.stop_reason == "runtime_exhausted"
    assert result.items == []
    assert transport.calls == [feed]


def test_hacker_news_commands_are_registered_in_main_cli() -> None:
    result = CliRunner().invoke(app, ["hacker-news", "--help"])

    assert result.exit_code == 0
    assert "smoke" in result.stdout


def test_hacker_news_smoke_writes_standard_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = SourceItem(
        external_id="hn-story-1",
        source_type=SourceType.POST,
        title="Ask HN: Invoice workflow",
        body="We manually copy invoices into a spreadsheet every month.",
        subreddit="hackernews",
        canonical_url="https://news.ycombinator.com/item?id=1",
    )
    collection = HackerNewsCollectionResult(
        items=[item],
        evidence=[
            HackerNewsEvidence(
                url=f"{API_BASE}/item/1.json",
                status="ok",
                detail="item fetched",
            )
        ],
        stop_reason=None,
    )

    class FakeCollector:
        def collect(
            self,
            *,
            policy: ResearchRun,
            feed: str,
        ) -> HackerNewsCollectionResult:
            assert policy.live_access_enabled is True
            assert feed == "askstories"
            return collection

    monkeypatch.setattr(
        "painfinder.hacker_news_cli.HackerNewsCollector",
        FakeCollector,
    )
    artifacts = tmp_path / "hn"
    result = CliRunner().invoke(
        app,
        [
            "hacker-news",
            "smoke",
            "--feed",
            "askstories",
            "--max-threads",
            "1",
            "--max-comments",
            "0",
            "--artifacts-dir",
            str(artifacts),
        ],
    )

    assert result.exit_code == 0
    assert "collected 1 item(s)" in result.stdout
    summary = json.loads(
        (artifacts / "collection-result.json").read_text(encoding="utf-8")
    )
    assert summary["source"] == "hacker_news"
    assert summary["stop_reason"] == "completed"
    assert (artifacts / "source-items.jsonl").exists()
    report = (artifacts / "opportunities.html").read_text(encoding="utf-8")
    assert "Opportunity Discovery Report" in report


def test_hacker_news_cli_rejects_unknown_feed(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "hacker-news",
            "smoke",
            "--feed",
            "unsupported",
            "--artifacts-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 2
    assert "unsupported feed" in result.stdout
