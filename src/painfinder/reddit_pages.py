from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from painfinder.browser_models import PageState, ThreadCandidate
from painfinder.domain import SourceItem, SourceType

BLOCK_PATTERNS = (
    "you've been blocked by network security",
    "whoa there, pardner",
    "request blocked",
)
CAPTCHA_PATTERNS = (
    "captcha",
    "prove you are human",
    "verify you are human",
)
LOGIN_PATTERNS = (
    "log in to continue",
    "sign in to continue",
)
RATE_LIMIT_PATTERNS = (
    "too many requests",
    "you are doing that too much",
)


def detect_page_state(html: str) -> PageState:
    lowered = html.lower()
    if any(pattern in lowered for pattern in BLOCK_PATTERNS):
        return PageState.BLOCKED
    if any(pattern in lowered for pattern in CAPTCHA_PATTERNS):
        return PageState.CAPTCHA
    if any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return PageState.RATE_LIMITED
    if any(pattern in lowered for pattern in LOGIN_PATTERNS):
        return PageState.LOGIN_WALL
    return PageState.NORMAL


def extract_old_reddit_listing(
    html: str,
    *,
    base_url: str = "https://old.reddit.com",
) -> list[ThreadCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ThreadCandidate] = []
    seen: set[str] = set()

    for thing in soup.select("div.thing[data-fullname]"):
        title_link = thing.select_one("a.title")
        if title_link is None:
            continue
        href = title_link.get("href")
        title = " ".join(title_link.get_text(" ", strip=True).split())
        if not href or not title:
            continue

        absolute = urljoin(base_url, str(href))
        if "/comments/" not in absolute or absolute in seen:
            continue

        subreddit = thing.get("data-subreddit")
        candidates.append(
            ThreadCandidate(
                title=title,
                url=HttpUrl(absolute),
                subreddit=str(subreddit) if subreddit else None,
            )
        )
        seen.add(absolute)

    return candidates


def extract_old_reddit_thread(
    html: str,
    *,
    page_url: str,
    max_comments: int,
) -> list[SourceItem]:
    soup = BeautifulSoup(html, "html.parser")
    post = soup.select_one("div.thing.link[data-fullname]")
    if post is None:
        return []

    post_id = str(post.get("data-fullname") or "")
    title_element = post.select_one("a.title")
    body_element = post.select_one("div.usertext-body")
    subreddit = post.get("data-subreddit")

    items = [
        SourceItem(
            external_id=post_id or page_url,
            source_type=SourceType.POST,
            title=_text(title_element),
            body=_text(body_element),
            subreddit=str(subreddit) if subreddit else None,
            canonical_url=HttpUrl(page_url),
        )
    ]

    for comment in soup.select("div.comment[data-fullname]")[:max_comments]:
        body = _text(comment.select_one("div.usertext-body"))
        if not body or body in {"[deleted]", "[removed]"}:
            continue

        permalink = comment.select_one("a.bylink")
        href = permalink.get("href") if permalink else None
        canonical = urljoin(page_url, str(href)) if href else page_url
        items.append(
            SourceItem(
                external_id=str(comment.get("data-fullname") or canonical),
                source_type=SourceType.COMMENT,
                body=body,
                subreddit=str(subreddit) if subreddit else None,
                canonical_url=HttpUrl(canonical),
            )
        )
    return items


def _text(element: Tag | None) -> str:
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())
