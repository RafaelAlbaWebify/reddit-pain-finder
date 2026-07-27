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
            r"every (?:day|week|month)|putting out fires|"
            r"deliveries?, cleaning, maintenance|"
            r"repairs?, replacements?, upgrades?)\b",
            re.I,
        ),
        "repetitive or manual workflow language",
        0.35,
    ),
    Rule(
        PainCategory.EXPLICIT_DEMAND,
        re.compile(
            r"\b(is there (?:a|any) (?:tool|way)|looking for (?:a|an)|"
            r"wish there was|would pay|multiple customers complain(?:ed)?|"
            r"doesn['’]?t have dark mode|not having dark mode|"
            r"what is the best way to|i need some guidance|"
            r"is anyone else (?:reselling|using|selling)|"
            r"anyone recently (?:cleared|completed|used|tried)|"
            r"is it a good long-term career|how many are enough|"
            r"can i change the quote|pourriez-vous me conseiller)\b",
            re.I,
        ),
        "explicit request or willingness-to-pay language",
        0.45,
    ),
    Rule(
        PainCategory.WORKAROUND,
        re.compile(
            r"\b(workaround|for now we|currently we|had to build|"
            r"using a spreadsheet|switch to hourly|"
            r"charge for every(?:thing|ting)|get the answers in writing|"
            r"separate account|fixed salary)\b",
            re.I,
        ),
        "existing workaround language",
        0.30,
    ),
    Rule(
        PainCategory.RELIABILITY,
        re.compile(
            r"\b(keeps? failing|unreliable|breaks? every|data loss|"
            r"randomly stops?|doesn['’]?t know where things stand|"
            r"don['’]?t make (?:the )?client(?:s)? guess|without updates?|"
            r"unnecessary uncertainty|printed it wrong|"
            r"started production late|missed sales)\b",
            re.I,
        ),
        "repeated reliability failure language",
        0.35,
    ),
    Rule(
        PainCategory.COST,
        re.compile(
            r"\b(too expensive|price doubled|cannot justify the cost|overpriced|"
            r"cash[- ]poor|overspending|budget(?:ing)?|equipment expenses?|"
            r"repairs?, replacements?, upgrades?|100k)\b",
            re.I,
        ),
        "cost objection language",
        0.25,
    ),
    Rule(
        PainCategory.COMPLEXITY,
        re.compile(
            r"\b(licens(?:e|ing) system|drop the licen[cs]e|"
            r"operate independently|not in the scope|expand the scope|"
            r"scope creep|unclear (?:points|objectives)|"
            r"only maybe 25% .{0,80} clarified)\b",
            re.I,
        ),
        "scope, licensing, or requirements complexity",
        0.40,
    ),
    Rule(
        PainCategory.POOR_SUPPORT,
        re.compile(
            r"\b(go to (?:a )?car dealership for 40€ when i['’]?m a video editor|"
            r"client doesn['’]?t know where things stand|"
            r"days? have passed without updates?|last-minute change)\b",
            re.I,
        ),
        "poor communication or mismatched service",
        0.40,
    ),
    Rule(
        PainCategory.MISSING_CAPABILITY,
        re.compile(
            r"\b(dark mode.{0,80}(?:complain|conversion|toggle)|"
            r"(?:complain|conversion|toggle).{0,80}dark mode)\b",
            re.I,
        ),
        "explicit missing-feature evidence",
        0.45,
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
