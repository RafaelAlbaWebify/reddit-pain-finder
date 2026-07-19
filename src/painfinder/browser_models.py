from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class PageState(StrEnum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    LOGIN_WALL = "login_wall"
    RATE_LIMITED = "rate_limited"
    SELECTOR_MISMATCH = "selector_mismatch"


class BrowserEvidence(BaseModel):
    url: HttpUrl
    state: PageState
    title: str = ""
    screenshot_path: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: list[str] = Field(default_factory=list)


class ThreadCandidate(BaseModel):
    title: str
    url: HttpUrl
    subreddit: str | None = None
