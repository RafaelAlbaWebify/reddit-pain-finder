from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from painfinder.collection import CollectionBudget, StopReason
from painfinder.domain import ResearchRun, SourceItem, SourceType

API_BASE = "https://hacker-news.firebaseio.com/v0"
API_HOST = "hacker-news.firebaseio.com"
ALLOWED_FEEDS = {"topstories", "newstories", "beststories", "askstories"}


class JsonTransport(Protocol):
    def get_json(self, url: str) -> Any:
        """Return decoded JSON for one approved API URL."""


@dataclass(frozen=True)
class HackerNewsEvidence:
    url: str
    status: str
    detail: str


@dataclass(frozen=True)
class HackerNewsCollectionResult:
    items: list[SourceItem]
    evidence: list[HackerNewsEvidence]
    stop_reason: str | None


class UrllibJsonTransport:
    def get_json(self, url: str) -> Any:
        _ensure_allowed_url(url)
        request = Request(
            url,
            headers={"User-Agent": "reddit-pain-finder/0.2 read-only research"},
        )
        with urlopen(request, timeout=20) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))


class HackerNewsCollector:
    def __init__(
        self,
        *,
        transport: JsonTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport or UrllibJsonTransport()
        self.sleep = sleep
        self.clock = clock

    def collect(
        self,
        *,
        policy: ResearchRun,
        feed: str = "askstories",
    ) -> HackerNewsCollectionResult:
        if policy.concurrency != 1:
            raise ValueError("Hacker News collection requires concurrency=1")
        if not policy.live_access_enabled:
            raise ValueError("Live access must be explicitly enabled")
        if feed not in ALLOWED_FEEDS:
            raise ValueError(f"Unsupported Hacker News feed: {feed}")

        started_at = self.clock()
        budget = CollectionBudget(policy)
        evidence: list[HackerNewsEvidence] = []
        items: list[SourceItem] = []
        feed_url = f"{API_BASE}/{feed}.json"

        if self._runtime_exhausted(policy, started_at):
            return HackerNewsCollectionResult(
                items,
                evidence,
                StopReason.RUNTIME_EXHAUSTED.value,
            )
        stop = budget.register_page()
        if stop is not None:
            return HackerNewsCollectionResult(items, evidence, stop.value)

        try:
            story_ids = self.transport.get_json(feed_url)
        except HTTPError as error:
            return self._http_failure(feed_url, error, items, evidence)
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            evidence.append(HackerNewsEvidence(feed_url, "network_error", str(error)))
            return HackerNewsCollectionResult(items, evidence, "network_error")

        if self._runtime_exhausted(policy, started_at):
            return HackerNewsCollectionResult(
                items,
                evidence,
                StopReason.RUNTIME_EXHAUSTED.value,
            )
        if not isinstance(story_ids, list):
            evidence.append(
                HackerNewsEvidence(feed_url, "malformed", "feed was not a list")
            )
            return HackerNewsCollectionResult(items, evidence, "malformed_response")

        for raw_story_id in story_ids:
            if not _is_integer_id(raw_story_id):
                continue
            if self._runtime_exhausted(policy, started_at):
                return HackerNewsCollectionResult(
                    items,
                    evidence,
                    StopReason.RUNTIME_EXHAUSTED.value,
                )
            stop = budget.register_page(is_thread=True)
            if stop is not None:
                return HackerNewsCollectionResult(items, evidence, stop.value)
            story_url = f"{API_BASE}/item/{raw_story_id}.json"
            story = self._fetch_item(story_url, evidence)
            if story is None:
                if evidence and evidence[-1].status in {"blocked", "rate_limited"}:
                    return HackerNewsCollectionResult(
                        items,
                        evidence,
                        evidence[-1].status,
                    )
                continue
            if self._runtime_exhausted(policy, started_at):
                return HackerNewsCollectionResult(
                    items,
                    evidence,
                    StopReason.RUNTIME_EXHAUSTED.value,
                )
            source = _story_to_source_item(story)
            if source is None:
                continue
            items.append(source)

            comment_ids = story.get("kids", [])
            if not isinstance(comment_ids, list):
                continue
            collected_comments = 0
            for raw_comment_id in comment_ids:
                if collected_comments >= policy.max_comments_per_thread:
                    break
                if not _is_integer_id(raw_comment_id):
                    continue
                if self._runtime_exhausted(policy, started_at):
                    return HackerNewsCollectionResult(
                        items,
                        evidence,
                        StopReason.RUNTIME_EXHAUSTED.value,
                    )
                stop = budget.register_page()
                if stop is not None:
                    return HackerNewsCollectionResult(items, evidence, stop.value)
                comment_url = f"{API_BASE}/item/{raw_comment_id}.json"
                comment = self._fetch_item(comment_url, evidence)
                if comment is None:
                    if evidence and evidence[-1].status in {
                        "blocked",
                        "rate_limited",
                    }:
                        return HackerNewsCollectionResult(
                            items,
                            evidence,
                            evidence[-1].status,
                        )
                    continue
                if self._runtime_exhausted(policy, started_at):
                    return HackerNewsCollectionResult(
                        items,
                        evidence,
                        StopReason.RUNTIME_EXHAUSTED.value,
                    )
                source_comment = _comment_to_source_item(comment)
                if source_comment is None:
                    continue
                items.append(source_comment)
                collected_comments += 1
                self.sleep(policy.min_delay_seconds)

            self.sleep(policy.min_delay_seconds)

        return HackerNewsCollectionResult(items, evidence, None)

    def _runtime_exhausted(self, policy: ResearchRun, started_at: float) -> bool:
        return self.clock() - started_at >= policy.max_runtime_seconds

    def _fetch_item(
        self,
        url: str,
        evidence: list[HackerNewsEvidence],
    ) -> dict[str, Any] | None:
        try:
            payload = self.transport.get_json(url)
        except HTTPError as error:
            status = _http_status(error.code)
            evidence.append(HackerNewsEvidence(url, status, f"HTTP {error.code}"))
            return None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            evidence.append(HackerNewsEvidence(url, "network_error", str(error)))
            return None
        if not isinstance(payload, dict):
            evidence.append(
                HackerNewsEvidence(url, "malformed", "item was not an object")
            )
            return None
        evidence.append(HackerNewsEvidence(url, "ok", "item fetched"))
        return payload

    def _http_failure(
        self,
        url: str,
        error: HTTPError,
        items: list[SourceItem],
        evidence: list[HackerNewsEvidence],
    ) -> HackerNewsCollectionResult:
        status = _http_status(error.code)
        evidence.append(HackerNewsEvidence(url, status, f"HTTP {error.code}"))
        return HackerNewsCollectionResult(items, evidence, status)


def _http_status(code: int) -> str:
    if code == 429:
        return "rate_limited"
    if code == 403:
        return "blocked"
    return "http_error"


def _story_to_source_item(payload: dict[str, Any]) -> SourceItem | None:
    if payload.get("deleted") or payload.get("dead"):
        return None
    item_type = payload.get("type")
    if item_type not in (None, "story"):
        return None
    item_id = payload.get("id")
    title = _clean_text(payload.get("title"))
    text = _clean_html(payload.get("text"))
    if not _is_integer_id(item_id) or not title:
        return None
    return SourceItem(
        external_id=f"hn-story-{item_id}",
        source_type=SourceType.POST,
        title=title,
        body=text or title,
        subreddit="hackernews",
        canonical_url=f"https://news.ycombinator.com/item?id={item_id}",
    )


def _comment_to_source_item(payload: dict[str, Any]) -> SourceItem | None:
    if payload.get("deleted") or payload.get("dead"):
        return None
    item_type = payload.get("type")
    if item_type not in (None, "comment"):
        return None
    item_id = payload.get("id")
    text = _clean_html(payload.get("text"))
    if not _is_integer_id(item_id) or not text:
        return None
    return SourceItem(
        external_id=f"hn-comment-{item_id}",
        source_type=SourceType.COMMENT,
        title="",
        body=text,
        subreddit="hackernews",
        canonical_url=f"https://news.ycombinator.com/item?id={item_id}",
    )


def _is_integer_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _clean_html(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(BeautifulSoup(str(value), "html.parser").get_text(" ").split())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _ensure_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != API_HOST
        or not parsed.path.startswith("/v0/")
        or not parsed.path.endswith(".json")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"URL outside approved Hacker News API is forbidden: {url}")
