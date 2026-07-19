from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl

from painfinder.domain import SourceItem, SourceType


class FixtureExtractionError(RuntimeError):
    pass


def extract_thread_fixture(path: Path) -> list[SourceItem]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    base_url = soup.body.get("data-source-url") if soup.body else None
    if not base_url:
        raise FixtureExtractionError("Fixture is missing body[data-source-url]")

    post = soup.select_one("[data-testid='post-container']")
    if post is None:
        raise FixtureExtractionError("Fixture contains no post container")

    items = [
        SourceItem(
            external_id=_required(post, "data-item-id"),
            source_type=SourceType.POST,
            title=_text(post.select_one("[data-role='post-title']")),
            body=_text(post.select_one("[data-role='post-body']")),
            subreddit=_optional(post, "data-subreddit"),
            canonical_url=HttpUrl(
                urljoin(
                    str(base_url),
                    _optional(post, "data-permalink") or "",
                )
            ),
        )
    ]

    for comment in soup.select("[data-testid='comment']"):
        body = _text(comment.select_one("[data-role='comment-body']"))
        if not body:
            continue
        items.append(
            SourceItem(
                external_id=_required(comment, "data-item-id"),
                source_type=SourceType.COMMENT,
                body=body,
                subreddit=_optional(post, "data-subreddit"),
                canonical_url=HttpUrl(
                    urljoin(
                        str(base_url),
                        _optional(comment, "data-permalink") or "",
                    )
                ),
            )
        )
    return items


def _optional(element: Tag, attribute: str) -> str | None:
    value = element.get(attribute)
    return str(value) if value else None


def _required(element: Tag, attribute: str) -> str:
    value = _optional(element, attribute)
    if not value:
        raise FixtureExtractionError(f"Missing required attribute: {attribute}")
    return value


def _text(element: Tag | None) -> str:
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())
