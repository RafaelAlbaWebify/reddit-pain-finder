from __future__ import annotations

import re
from dataclasses import dataclass

from painfinder.domain import PainCategory, PainSignal, SourceItem


@dataclass(frozen=True)
class Rule:
    category: PainCategory
    pattern: re.Pattern[str]
    reason: str
    weight: float


RULES = (
    Rule(
        PainCategory.MANUAL_WORK,
        re.compile(
            r"\b(manually|copy(?:ing)? and paste|spreadsheet|"
            r"every (?:day|week|month))\b",
            re.I,
        ),
        "repetitive or manual workflow language",
        0.35,
    ),
    Rule(
        PainCategory.EXPLICIT_DEMAND,
        re.compile(
            r"\b(is there (?:a|any) (?:tool|way)|looking for (?:a|an)|"
            r"wish there was|would pay)\b",
            re.I,
        ),
        "explicit request or willingness-to-pay language",
        0.45,
    ),
    Rule(
        PainCategory.WORKAROUND,
        re.compile(
            r"\b(workaround|for now we|currently we|had to build|"
            r"using a spreadsheet)\b",
            re.I,
        ),
        "existing workaround language",
        0.30,
    ),
    Rule(
        PainCategory.RELIABILITY,
        re.compile(
            r"\b(keeps? failing|unreliable|breaks? every|data loss|"
            r"randomly stops?)\b",
            re.I,
        ),
        "repeated reliability failure language",
        0.35,
    ),
    Rule(
        PainCategory.COST,
        re.compile(
            r"\b(too expensive|price doubled|cannot justify the cost|overpriced)\b",
            re.I,
        ),
        "cost objection language",
        0.25,
    ),
)


def detect_pain_signals(items: list[SourceItem]) -> list[PainSignal]:
    results: list[PainSignal] = []
    for item in items:
        text = " ".join(part for part in (item.title, item.body) if part)
        matches = [rule for rule in RULES if rule.pattern.search(text)]
        if not matches:
            continue

        strongest = max(matches, key=lambda rule: rule.weight)
        confidence = min(0.95, 0.35 + sum(rule.weight for rule in matches))
        results.append(
            PainSignal(
                source_external_id=item.external_id,
                excerpt=text[:500],
                category=strongest.category,
                confidence=round(confidence, 2),
                reasons=[rule.reason for rule in matches],
            )
        )
    return results
