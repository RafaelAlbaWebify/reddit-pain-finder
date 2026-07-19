# Architecture — Vertical Slice 0

## Product boundary

The product discovers candidate customer pains from bounded public Reddit research and later validates possible solutions. A discovered pain is evidence for a hypothesis, not proof of a market.

## Current modules

- `domain.py`: stable concepts and validation.
- `collection.py`: navigation host restrictions and collection budgets.
- `reddit_fixture.py`: offline extraction contract.
- `analysis.py`: deterministic baseline pain detection.
- `report.py`: traceable evidence output.
- `live.py`: intentionally disabled boundary for the future Playwright collector.

## Invariants

1. External collection is read-only.
2. Live collection is disabled by default.
3. Every collected item has a canonical source URL.
4. Collection budgets are explicit and validated.
5. Navigation outside approved Reddit hosts is rejected.
6. Analysis never controls browser navigation.
7. Reports state whether evidence came from fixtures or live collection.
8. Browser failures are not represented as “no pain found.”

## Next acceptance gate

Live collection may be implemented only after tests exist for:

- allowed host enforcement;
- maximum page/thread/comment budgets;
- selector mismatch;
- block page;
- CAPTCHA page;
- login wall;
- user cancellation;
- Playwright trace retention;
- screenshot retention;
- three-thread headed smoke run.
