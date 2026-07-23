from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from pydantic import HttpUrl

from painfinder.browser_models import PageState, ThreadCandidate
from painfinder.domain import SourceItem, SourceType
from painfinder.reddit_pages import (
    BLOCK_PATTERNS,
    CAPTCHA_PATTERNS,
    LOGIN_PATTERNS,
    RATE_LIMIT_PATTERNS,
)


def detect_reddit_response_state(*, status: int, body: str) -> PageState:
    lowered = body.lower()
    if status == 429 or any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return PageState.RATE_LIMITED
    if any(pattern in lowered for pattern in CAPTCHA_PATTERNS):
        return PageState.CAPTCHA
    if any(pattern in lowered for pattern in LOGIN_PATTERNS):
        return PageState.LOGIN_WALL
    if status in {401, 403} or any(pattern in lowered for pattern in BLOCK_PATTERNS):
        return PageState.BLOCKED
    return PageState.NORMAL


def extract_reddit_listing_json(
    payload: Any,
    *,
    base_url: str = "https://www.reddit.com",
) -> list[ThreadCandidate]:
    listing = _listing_data(payload)
    candidates: list[ThreadCandidate] = []
    seen: set[str] = set()

    for child in listing.get("children", []):
        if not isinstance(child, dict):
            continue
        data = child.get("data")
        if not isinstance(data, dict):
            continue

        title = _clean_text(data.get("title"))
        permalink = data.get("permalink")
        if not title or not isinstance(permalink, str):
            continue

        absolute = urljoin(base_url, permalink)
        if "/comments/" not in absolute or absolute in seen:
            continue

        subreddit = data.get("subreddit")
        candidates.append(
            ThreadCandidate(
                title=title,
                url=HttpUrl(absolute),
                subreddit=str(subreddit) if subreddit else None,
            )
        )
        seen.add(absolute)

    return candidates


def extract_reddit_thread_json(
    payload: Any,
    *,
    page_url: str,
    max_comments: int,
    base_url: str = "https://www.reddit.com",
) -> list[SourceItem]:
    if not isinstance(payload, list) or not payload:
        return []

    post_listing = _listing_data(payload[0])
    post_children = post_listing.get("children", [])
    if not post_children:
        return []

    post_wrapper = post_children[0]
    if not isinstance(post_wrapper, dict):
        return []
    post = post_wrapper.get("data")
    if not isinstance(post, dict):
        return []

    post_permalink = post.get("permalink")
    post_url = (
        urljoin(base_url, post_permalink)
        if isinstance(post_permalink, str)
        else page_url
    )
    subreddit = post.get("subreddit")
    post_id = _clean_text(post.get("name")) or _clean_text(post.get("id")) or page_url

    items = [
        SourceItem(
            external_id=post_id,
            source_type=SourceType.POST,
            title=_clean_text(post.get("title")),
            body=_clean_text(post.get("selftext")),
            subreddit=str(subreddit) if subreddit else None,
            canonical_url=HttpUrl(post_url),
        )
    ]

    if max_comments <= 0 or len(payload) < 2:
        return items

    comment_listing = _listing_data(payload[1])
    comment_count = 0

    for comment in _walk_comments(comment_listing.get("children", [])):
        body = _clean_text(comment.get("body"))
        if not body or body in {"[deleted]", "[removed]"}:
            continue

        permalink = comment.get("permalink")
        canonical = (
            urljoin(base_url, permalink)
            if isinstance(permalink, str)
            else page_url
        )
        external_id = (
            _clean_text(comment.get("name"))
            or _clean_text(comment.get("id"))
            or canonical
        )
        comment_subreddit = comment.get("subreddit") or subreddit

        items.append(
            SourceItem(
                external_id=external_id,
                source_type=SourceType.COMMENT,
                body=body,
                subreddit=str(comment_subreddit) if comment_subreddit else None,
                canonical_url=HttpUrl(canonical),
            )
        )
        comment_count += 1
        if comment_count >= max_comments:
            break

    return items


def _listing_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("kind") != "Listing":
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _walk_comments(children: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(children, list):
        return

    for wrapper in children:
        if not isinstance(wrapper, dict) or wrapper.get("kind") != "t1":
            continue
        data = wrapper.get("data")
        if not isinstance(data, dict):
            continue

        yield data

        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_listing = _listing_data(replies)
            yield from _walk_comments(reply_listing.get("children", []))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())
