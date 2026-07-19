from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import quote

from playwright.async_api import Page, async_playwright
from pydantic import HttpUrl

from painfinder.browser_models import BrowserEvidence, PageState
from painfinder.collection import CollectionBudget, ensure_allowed_reddit_url
from painfinder.domain import ResearchRun, SourceItem
from painfinder.reddit_pages import (
    detect_page_state,
    extract_old_reddit_listing,
    extract_old_reddit_thread,
)


class LiveCollectionStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveCollectionResult:
    items: list[SourceItem]
    evidence: list[BrowserEvidence]
    stop_reason: str | None


class PlaywrightRedditCollector:
    def __init__(self, *, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def collect(
        self,
        *,
        policy: ResearchRun,
        subreddits: list[str],
        sort: str = "new",
    ) -> LiveCollectionResult:
        return asyncio.run(
            self._collect(
                policy=policy,
                subreddits=subreddits,
                sort=sort,
            )
        )

    async def _collect(
        self,
        *,
        policy: ResearchRun,
        subreddits: list[str],
        sort: str,
    ) -> LiveCollectionResult:
        if not policy.live_access_enabled:
            raise LiveCollectionStopped("Live collection is disabled by policy.")
        if not subreddits:
            raise ValueError("At least one seed subreddit is required.")
        if sort not in {"new", "hot", "rising"}:
            raise ValueError("sort must be one of: new, hot, rising")

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        profile = self.artifacts_dir / "browser-profile"
        traces = self.artifacts_dir / "traces"
        screenshots = self.artifacts_dir / "screenshots"
        traces.mkdir(exist_ok=True)
        screenshots.mkdir(exist_ok=True)

        budget = CollectionBudget(policy)
        items: list[SourceItem] = []
        evidence: list[BrowserEvidence] = []
        started = monotonic()

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=profile,
                headless=False,
                viewport={"width": 1440, "height": 1000},
            )
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            try:
                for subreddit in subreddits:
                    if monotonic() - started >= policy.max_runtime_seconds:
                        return LiveCollectionResult(items, evidence, "runtime_budget_exhausted")

                    listing_url = (
                        f"https://old.reddit.com/r/{quote(subreddit)}/{sort}/"
                    )
                    stop = budget.register_page()
                    if stop:
                        return LiveCollectionResult(items, evidence, stop.value)

                    page = await context.new_page()
                    state = await self._navigate_and_capture(
                        page=page,
                        url=listing_url,
                        evidence=evidence,
                        screenshots=screenshots,
                    )
                    if state is not PageState.NORMAL:
                        return LiveCollectionResult(items, evidence, state.value)

                    listing_html = await page.content()
                    candidates = extract_old_reddit_listing(listing_html)

                    for candidate in candidates:
                        if budget.threads_collected >= policy.max_threads:
                            return LiveCollectionResult(
                                items,
                                evidence,
                                "thread_budget_exhausted",
                            )
                        if monotonic() - started >= policy.max_runtime_seconds:
                            return LiveCollectionResult(
                                items,
                                evidence,
                                "runtime_budget_exhausted",
                            )

                        url = str(candidate.url)
                        ensure_allowed_reddit_url(url)
                        stop = budget.register_page(is_thread=True)
                        if stop:
                            return LiveCollectionResult(items, evidence, stop.value)

                        await asyncio.sleep(policy.min_delay_seconds)
                        state = await self._navigate_and_capture(
                            page=page,
                            url=url,
                            evidence=evidence,
                            screenshots=screenshots,
                        )
                        if state is not PageState.NORMAL:
                            return LiveCollectionResult(items, evidence, state.value)

                        thread_items = extract_old_reddit_thread(
                            await page.content(),
                            page_url=url,
                            max_comments=policy.max_comments_per_thread,
                        )
                        if not thread_items:
                            evidence[-1].state = PageState.SELECTOR_MISMATCH
                            evidence[-1].details.append(
                                "No old-Reddit thread container was found."
                            )
                            return LiveCollectionResult(
                                items,
                                evidence,
                                PageState.SELECTOR_MISMATCH.value,
                            )
                        items.extend(thread_items)

                return LiveCollectionResult(items, evidence, None)
            finally:
                trace_path = traces / "collection-trace.zip"
                await context.tracing.stop(path=trace_path)
                await context.close()

    async def _navigate_and_capture(
        self,
        *,
        page: Page,
        url: str,
        evidence: list[BrowserEvidence],
        screenshots: Path,
    ) -> PageState:
        ensure_allowed_reddit_url(url)
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        html = await page.content()
        state = detect_page_state(html)
        screenshot = screenshots / f"page-{len(evidence) + 1:03d}.png"
        await page.screenshot(path=screenshot, full_page=True)

        evidence.append(
            BrowserEvidence(
                url=HttpUrl(url),
                state=state,
                title=await page.title(),
                screenshot_path=str(screenshot),
            )
        )
        return state
