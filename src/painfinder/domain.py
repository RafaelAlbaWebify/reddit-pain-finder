from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SourceType(StrEnum):
    POST = "post"
    COMMENT = "comment"


class PainCategory(StrEnum):
    MANUAL_WORK = "manual_work"
    RELIABILITY = "reliability"
    COST = "cost"
    COMPLEXITY = "complexity"
    MISSING_CAPABILITY = "missing_capability"
    POOR_SUPPORT = "poor_support"
    WORKAROUND = "workaround"
    EXPLICIT_DEMAND = "explicit_demand"


class ResearchRun(BaseModel):
    name: str = Field(min_length=1)
    max_pages: int = Field(default=25, ge=1, le=500)
    max_threads: int = Field(default=10, ge=1, le=100)
    max_comments_per_thread: int = Field(default=30, ge=0, le=500)
    concurrency: int = Field(default=1, ge=1, le=2)
    min_delay_seconds: float = Field(default=2.0, ge=0.5, le=60)
    max_runtime_seconds: int = Field(default=900, ge=30, le=7200)
    live_access_enabled: bool = False

    @model_validator(mode="after")
    def enforce_safe_defaults(self) -> ResearchRun:
        if self.live_access_enabled and self.concurrency != 1:
            raise ValueError("Live collection requires concurrency=1")
        return self


class SourceItem(BaseModel):
    external_id: str = Field(min_length=1)
    source_type: SourceType
    title: str = ""
    body: str
    subreddit: str | None = None
    canonical_url: HttpUrl
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def content_hash(self) -> str:
        normalized = " ".join(f"{self.title} {self.body}".lower().split())
        return sha256(normalized.encode("utf-8")).hexdigest()


class PainSignal(BaseModel):
    source_external_id: str
    excerpt: str = Field(min_length=1)
    category: PainCategory
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1)
