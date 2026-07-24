from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import quote

from playwright.async_api import Page, async_playwright
from pydantic import HttpUrl

from painfinder.browser_models import BrowserEvidence, PageState
from painfinder.collection import CollectionBudget, ensure_allowed_reddit_url
from painfinder.domain import ResearchRun, SourceItem
from painfinder.reddit_json import (
    detect_reddit_response_state,
    extract_reddit_listing_json,
    extract_reddit_thread_json,
)
from painfinder.reddit_pages import detect_page_state


class LiveCollectionStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveCollectionResult:
    items: list[SourceItem]
    evidence: list[BrowserEvidence]
    stop_reason: str | None


def resolve_navigation_state(
    *,
    status: int | None,
    detected_state: PageState,
) -> PageState:
    if status in {401, 403}:
        return PageState.BLOCKED
    if status == 429:
        return PageState.RATE_LIMITED
    if (
        status is not None
        and 200 <= status < 300
        and detected_state is PageState.BLOCKED
    ):
        return PageState.NORMAL
    return detected_state


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
        traces = self.artifacts_dir / "traces"
        screenshots = self.artifacts_dir / "screenshots"
        traces.mkdir(exist_ok=True)
        screenshots.mkdir(exist_ok=True)

        budget = CollectionBudget(policy)
        items: list[SourceItem] = []
        evidence: list[BrowserEvidence] = []
        started = monotonic()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context(
                locale="en-US",
                viewport={"width": 1440, "height": 1000},
            )
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            try:
                page = await context.new_page()
                for subreddit in subreddits:
                    if monotonic() - started >= policy.max_runtime_seconds:
                        return LiveCollectionResult(items, evidence, "runtime_budget_exhausted")

                    html_url = f"https://www.reddit.com/r/{quote(subreddit)}/{sort}/"
                    stop = budget.register_page()
                    if stop:
                        return LiveCollectionResult(items, evidence, stop.value)

                    state = await self._navigate_and_capture(
                        page=page,
                        url=html_url,
                        evidence=evidence,
                        screenshots=screenshots,
                    )
                    if state is not PageState.NORMAL:
                        return LiveCollectionResult(items, evidence, state.value)

                    await asyncio.sleep(policy.min_delay_seconds)

                    listing_url = (
                        f"https://www.reddit.com/r/{quote(subreddit)}/{sort}.json"
                        "?limit=5&raw_json=1"
                    )
                    stop = budget.register_page()
                    if stop:
                        return LiveCollectionResult(items, evidence, stop.value)

                    listing_payload, state = await self._request_json_and_capture(
                        page=page,
                        url=listing_url,
                        evidence=evidence,
                    )
                    if state is not PageState.NORMAL:
                        return LiveCollectionResult(items, evidence, state.value)
                    if listing_payload is None:
                        return LiveCollectionResult(
                            items,
                            evidence,
                            PageState.SELECTOR_MISMATCH.value,
                        )

                    candidates = extract_reddit_listing_json(listing_payload)
                    if not candidates:
                        evidence[-1].state = PageState.SELECTOR_MISMATCH
                        evidence[-1].details.append(
                            "No Reddit JSON listing candidates were found."
                        )
                        return LiveCollectionResult(
                            items,
                            evidence,
                            PageState.SELECTOR_MISMATCH.value,
                        )

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

                        thread_url = f"{str(candidate.url).rstrip('/')}.json?raw_json=1"
                        ensure_allowed_reddit_url(thread_url)
                        stop = budget.register_page(is_thread=True)
                        if stop:
                            return LiveCollectionResult(items, evidence, stop.value)

                        await asyncio.sleep(policy.min_delay_seconds)
                        thread_payload, state = await self._request_json_and_capture(
                            page=page,
                            url=thread_url,
                            evidence=evidence,
                        )
                        if state is not PageState.NORMAL:
                            return LiveCollectionResult(items, evidence, state.value)
                        if thread_payload is None:
                            return LiveCollectionResult(
                                items,
                                evidence,
                                PageState.SELECTOR_MISMATCH.value,
                            )

                        thread_items = extract_reddit_thread_json(
                            thread_payload,
                            page_url=str(candidate.url),
                            max_comments=policy.max_comments_per_thread,
                        )
                        if not thread_items:
                            evidence[-1].state = PageState.SELECTOR_MISMATCH
                            evidence[-1].details.append(
                                "No Reddit JSON thread post was found."
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
                await browser.close()

    async def _navigate_and_capture(
        self,
        *,
        page: Page,
        url: str,
        evidence: list[BrowserEvidence],
        screenshots: Path,
    ) -> PageState:
        ensure_allowed_reddit_url(url)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        visible_text = await page.locator("body").inner_text(timeout=10_000)
        state = detect_page_state(visible_text)

        state = resolve_navigation_state(
            status=response.status if response is not None else None,
            detected_state=state,
        )

        screenshot = screenshots / f"page-{len(evidence) + 1:03d}.png"
        await page.screenshot(path=screenshot, full_page=True)

        details = []
        if response is not None:
            details.append(f"HTTP status: {response.status}")
            details.append(f"Final URL: {response.url}")

        evidence.append(
            BrowserEvidence(
                url=HttpUrl(url),
                state=state,
                title=await page.title(),
                screenshot_path=str(screenshot),
                details=details,
            )
        )
        return state

    async def _request_json_and_capture(
        self,
        *,
        page: Page,
        url: str,
        evidence: list[BrowserEvidence],
    ) -> tuple[object | None, PageState]:
        ensure_allowed_reddit_url(url)
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=45_000,
        )
        if response is None:
            state = PageState.SELECTOR_MISMATCH
            evidence.append(
                BrowserEvidence(
                    url=HttpUrl(url),
                    state=state,
                    title="Reddit JSON response",
                    details=["Navigation returned no HTTP response."],
                )
            )
            return None, state

        body = await response.text()
        state = detect_reddit_response_state(status=response.status, body=body)
        details = [
            f"HTTP status: {response.status}",
            f"Content-Type: {response.headers.get('content-type', '')}",
        ]

        payload: object | None = None
        if state is PageState.NORMAL:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as error:
                state = PageState.SELECTOR_MISMATCH
                details.append(f"Invalid JSON response: {error}")

        evidence.append(
            BrowserEvidence(
                url=HttpUrl(url),
                state=state,
                title="Reddit JSON response",
                details=details,
            )
        )
        return payload, state
