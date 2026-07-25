from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from painfinder.analysis import RULES
from painfinder.domain import (
    CandidateSignal,
    EvidenceField,
    EvidenceSpan,
    PainCategory,
    SignalType,
    SourceItem,
)


class CandidateGenerator(Protocol):
    detector_id: str
    detector_version: str

    def generate(self, item: SourceItem) -> tuple[CandidateSignal, ...]:
        ...


@dataclass(frozen=True)
class CandidatePattern:
    signal_type: SignalType
    pattern: re.Pattern[str]
    reason: str
    strength: float


@dataclass(frozen=True)
class RegexCandidateGenerator:
    detector_id: str
    detector_version: str
    patterns: tuple[CandidatePattern, ...]

    def generate(self, item: SourceItem) -> tuple[CandidateSignal, ...]:
        signals: list[CandidateSignal] = []
        for field, text in _evidence_fields(item):
            for candidate in self.patterns:
                match = candidate.pattern.search(text)
                if match is None:
                    continue
                signals.append(
                    CandidateSignal(
                        source_external_id=item.external_id,
                        signal_type=candidate.signal_type,
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        strength=candidate.strength,
                        evidence_spans=(
                            EvidenceSpan(
                                field=field,
                                start=match.start(),
                                end=match.end(),
                                text=match.group(0),
                            ),
                        ),
                        reason=candidate.reason,
                    )
                )
        return tuple(signals)


@dataclass(frozen=True)
class LegacyRuleCandidateGenerator:
    detector_id: str = "legacy-pain-rules"
    detector_version: str = "1"

    def generate(self, item: SourceItem) -> tuple[CandidateSignal, ...]:
        signals: list[CandidateSignal] = []
        for field, text in _evidence_fields(item):
            for rule in RULES:
                match = rule.pattern.search(text)
                if match is None:
                    continue
                signals.append(
                    CandidateSignal(
                        source_external_id=item.external_id,
                        signal_type=_legacy_signal_type(rule.category),
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        strength=min(1.0, 0.35 + rule.weight),
                        evidence_spans=(
                            EvidenceSpan(
                                field=field,
                                start=match.start(),
                                end=match.end(),
                                text=match.group(0),
                            ),
                        ),
                        reason=rule.reason,
                        metadata={"pain_category": rule.category.value},
                    )
                )
        return tuple(signals)


REQUEST_GENERATOR = RegexCandidateGenerator(
    detector_id="request-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.ADVICE_REQUEST,
            re.compile(
                r"\b(?:how (?:do|can|should|would) (?:i|we|you)|"
                r"what should (?:i|we)|who should|where can (?:i|we)|"
                r"has anyone (?:else )?(?:dealt with|experienced|found)|"
                r"any advice)\b",
                re.I,
            ),
            "request for guidance about an outcome or problem",
            0.62,
        ),
        CandidatePattern(
            SignalType.RECOMMENDATION_REQUEST,
            re.compile(
                r"\b(?:any recommendations?|what do you recommend|"
                r"can anyone recommend|which (?:tool|service|platform|option))\b",
                re.I,
            ),
            "request for a recommendation or alternative",
            0.68,
        ),
        CandidatePattern(
            SignalType.SOLUTION_REQUEST,
            re.compile(
                r"\b(?:is there (?:a|any) (?:tool|service|way|solution)|"
                r"looking for (?:a|an) (?:tool|service|platform|solution)|"
                r"need (?:a|an) (?:tool|service|way|solution))\b",
                re.I,
            ),
            "explicit request for a solution",
            0.78,
        ),
    ),
)

FAILURE_GENERATOR = RegexCandidateGenerator(
    detector_id="failure-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.FAILURE_NARRATIVE,
            re.compile(
                r"\b(?:failed|keeps? failing|stopped working|broke|"
                r"closed (?:my|our) account|blocked|rejected|"
                r"couldn['’]?t access|kept crashing|never received|"
                r"lost (?:access|data|money|sales)|bounced between)\b",
                re.I,
            ),
            "failure, interruption, rejection, or loss narrative",
            0.76,
        ),
        CandidatePattern(
            SignalType.POOR_SUPPORT,
            re.compile(
                r"\b(?:support (?:never|didn['’]?t|doesn['’]?t)|"
                r"sent (?:me|us) between|had to explain (?:it )?again|"
                r"no one owns|appeal (?:did nothing|failed)|"
                r"waiting for (?:an |a )?update)\b",
                re.I,
            ),
            "service ownership, response, or escalation failure",
            0.72,
        ),
    ),
)

OUTCOME_GENERATOR = RegexCandidateGenerator(
    detector_id="unmet-outcome-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.UNMET_OUTCOME,
            re.compile(
                r"\b(?:struggling to|having trouble|unable to|"
                r"can['’]?t (?:figure out|find|access|get|make|manage)|"
                r"not sure how|stuck (?:with|on|trying)|"
                r"trying to .{0,80} but)\b",
                re.I,
            ),
            "stated difficulty achieving a desired outcome",
            0.69,
        ),
        CandidatePattern(
            SignalType.UNCERTAINTY,
            re.compile(
                r"\b(?:i['’]?m not sure|we['’]?re not sure|"
                r"don['’]?t know how|confused about|unclear (?:how|what|why))\b",
                re.I,
            ),
            "uncertainty about a meaningful decision or process",
            0.56,
        ),
    ),
)

COST_GENERATOR = RegexCandidateGenerator(
    detector_id="cost-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.COST_PRESSURE,
            re.compile(
                r"\b(?:too costly|too expensive|can['’]?t afford|"
                r"unexpected fees?|price(?:s|d)? (?:increased|doubled)|"
                r"quote (?:increased|changed)|margin pressure|"
                r"not worth (?:the )?(?:price|cost)|pricing is confusing)\b",
                re.I,
            ),
            "explicit cost, affordability, pricing, or margin pressure",
            0.72,
        ),
        CandidatePattern(
            SignalType.MONEY_SIGNAL,
            re.compile(
                r"\b(?:would pay|willing to pay|paying for|"
                r"budget of|costs? us|revenue loss|lost revenue)\b",
                re.I,
            ),
            "explicit spending, willingness-to-pay, or financial-impact signal",
            0.66,
        ),
    ),
)

WORKAROUND_GENERATOR = RegexCandidateGenerator(
    detector_id="workaround-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.WORKAROUND,
            re.compile(
                r"\b(?:i ended up|we ended up|for now (?:i|we)|"
                r"we currently use|had to (?:build|create|switch)|"
                r"using .{0,40} instead|manually (?:tracking|copying|checking)|"
                r"keeping notes locally|built (?:my|our) own)\b",
                re.I,
            ),
            "current workaround or self-built substitute",
            0.73,
        ),
        CandidatePattern(
            SignalType.MANUAL_WORK,
            re.compile(
                r"\b(?:manually|copy(?:ing)? and past(?:e|ing)|"
                r"every (?:day|week|month)|spreadsheet|repetitive task)\b",
                re.I,
            ),
            "manual or repetitive workflow evidence",
            0.64,
        ),
    ),
)

CONFLICT_GENERATOR = RegexCandidateGenerator(
    detector_id="conflict-language",
    detector_version="1",
    patterns=(
        CandidatePattern(
            SignalType.CONFLICT,
            re.compile(
                r"\b(?:client (?:refuses|won['’]?t|keeps asking)|"
                r"customer (?:refuses|won['’]?t|keeps asking)|"
                r"argu(?:e|ing|ed) about|scope creep|"
                r"unpaid revisions?|not getting paid|payment dispute)\b",
                re.I,
            ),
            "client, customer, workplace, or payment conflict",
            0.70,
        ),
        CandidatePattern(
            SignalType.RISK_OR_FEAR,
            re.compile(
                r"\b(?:worried (?:that|about)|afraid (?:that|of)|"
                r"risk of|could lose|might lose|blocking sales|"
                r"compliance requirement)\b",
                re.I,
            ),
            "stated risk, fear, or business blocker",
            0.63,
        ),
    ),
)

DEFAULT_GENERATORS: tuple[CandidateGenerator, ...] = cast(
    tuple[CandidateGenerator, ...],
    (
        LegacyRuleCandidateGenerator(),
        REQUEST_GENERATOR,
        FAILURE_GENERATOR,
        OUTCOME_GENERATOR,
        COST_GENERATOR,
        WORKAROUND_GENERATOR,
        CONFLICT_GENERATOR,
    ),
)


def generate_candidate_signals(
    items: Sequence[SourceItem],
    generators: Sequence[CandidateGenerator] = DEFAULT_GENERATORS,
) -> list[CandidateSignal]:
    signals: list[CandidateSignal] = []
    for item in items:
        for generator in generators:
            signals.extend(generator.generate(item))
    return _deduplicate_signals(signals)


def group_candidate_signals(
    signals: Iterable[CandidateSignal],
) -> dict[str, tuple[CandidateSignal, ...]]:
    grouped: dict[str, list[CandidateSignal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.source_external_id].append(signal)
    return {
        external_id: tuple(
            sorted(
                values,
                key=lambda value: (
                    -value.strength,
                    value.detector_id,
                    value.signal_type.value,
                ),
            )
        )
        for external_id, values in sorted(grouped.items())
    }


def _evidence_fields(
    item: SourceItem,
) -> tuple[tuple[EvidenceField, str], ...]:
    fields: list[tuple[EvidenceField, str]] = []
    if item.title:
        fields.append((EvidenceField.TITLE, item.title))
    if item.body:
        fields.append((EvidenceField.BODY, item.body))
    return tuple(fields)


def _legacy_signal_type(category: PainCategory) -> SignalType:
    mapping = {
        PainCategory.MANUAL_WORK: SignalType.MANUAL_WORK,
        PainCategory.RELIABILITY: SignalType.FAILURE_NARRATIVE,
        PainCategory.COST: SignalType.COST_PRESSURE,
        PainCategory.COMPLEXITY: SignalType.EXPLICIT_PROBLEM,
        PainCategory.MISSING_CAPABILITY: SignalType.MISSING_CAPABILITY,
        PainCategory.POOR_SUPPORT: SignalType.POOR_SUPPORT,
        PainCategory.WORKAROUND: SignalType.WORKAROUND,
        PainCategory.EXPLICIT_DEMAND: SignalType.SOLUTION_REQUEST,
    }
    return mapping[category]


def _deduplicate_signals(
    signals: Iterable[CandidateSignal],
) -> list[CandidateSignal]:
    unique: dict[
        tuple[str, SignalType, str, EvidenceField, int, int],
        CandidateSignal,
    ] = {}
    for signal in signals:
        span = signal.evidence_spans[0]
        key = (
            signal.source_external_id,
            signal.signal_type,
            signal.detector_id,
            span.field,
            span.start,
            span.end,
        )
        existing = unique.get(key)
        if existing is None or signal.strength > existing.strength:
            unique[key] = signal
    return sorted(
        unique.values(),
        key=lambda value: (
            value.source_external_id,
            -value.strength,
            value.detector_id,
            value.signal_type.value,
        ),
    )
