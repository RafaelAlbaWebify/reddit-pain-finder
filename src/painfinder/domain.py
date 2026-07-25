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


class EvidenceField(StrEnum):
    TITLE = "title"
    BODY = "body"


class SignalType(StrEnum):
    EXPLICIT_PROBLEM = "explicit_problem"
    ADVICE_REQUEST = "advice_request"
    SOLUTION_REQUEST = "solution_request"
    RECOMMENDATION_REQUEST = "recommendation_request"
    FAILURE_NARRATIVE = "failure_narrative"
    UNMET_OUTCOME = "unmet_outcome"
    MANUAL_WORK = "manual_work"
    WORKAROUND = "workaround"
    COST_PRESSURE = "cost_pressure"
    MONEY_SIGNAL = "money_signal"
    UNCERTAINTY = "uncertainty"
    CONFLICT = "conflict"
    ACCESS_BARRIER = "access_barrier"
    MISSING_CAPABILITY = "missing_capability"
    POOR_SUPPORT = "poor_support"
    RISK_OR_FEAR = "risk_or_fear"
    DISSATISFACTION = "dissatisfaction"
    ALTERNATIVE_SEARCH = "alternative_search"


class EvidenceSpan(BaseModel):
    field: EvidenceField
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> EvidenceSpan:
        if self.end <= self.start:
            raise ValueError("Evidence span end must be greater than start")
        if len(self.text) != self.end - self.start:
            raise ValueError("Evidence span offsets must match text length")
        return self


class CandidateSignal(BaseModel):
    source_external_id: str = Field(min_length=1)
    signal_type: SignalType
    detector_id: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    strength: float = Field(ge=0, le=1)
    evidence_spans: tuple[EvidenceSpan, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


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
