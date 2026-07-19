from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from painfinder.domain import ResearchRun


class StopReason(StrEnum):
    BUDGET_EXHAUSTED = "budget_exhausted"
    BLOCK_DETECTED = "block_detected"
    CAPTCHA_DETECTED = "captcha_detected"
    LOGIN_WALL = "login_wall"
    SELECTOR_MISMATCH = "selector_mismatch"
    USER_CANCELLED = "user_cancelled"


@dataclass
class CollectionBudget:
    policy: ResearchRun
    pages_visited: int = 0
    threads_collected: int = 0

    def register_page(self, *, is_thread: bool = False) -> StopReason | None:
        if self.pages_visited >= self.policy.max_pages:
            return StopReason.BUDGET_EXHAUSTED
        if is_thread and self.threads_collected >= self.policy.max_threads:
            return StopReason.BUDGET_EXHAUSTED

        self.pages_visited += 1
        if is_thread:
            self.threads_collected += 1
        return None


def ensure_allowed_reddit_url(url: str) -> None:
    parsed = urlparse(url)
    allowed = {"reddit.com", "www.reddit.com", "old.reddit.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise ValueError(f"Navigation outside approved Reddit hosts is forbidden: {url}")
