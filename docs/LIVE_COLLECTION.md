# Live collection acceptance boundary

## Implemented

- headed Chromium persistent profile;
- normal `www.reddit.com` browser navigation to establish and capture the public page context;
- structured Reddit JSON listing and thread requests through Playwright's browser context;
- bounded page, thread, comment, delay, concurrency, and runtime policies;
- approved-host enforcement;
- HTTP-status plus explicit block, CAPTCHA, login-wall, and rate-limit detection;
- screenshot for every browser-navigated community page;
- evidence records for JSON requests, including status and content type;
- Playwright trace for every run;
- invalid-JSON and missing-listing stop conditions;
- generated HTML evidence report.

## Safety boundary

The collector is public, anonymous, read-only, and bounded. It does not log in, post,
vote, message, solve CAPTCHAs, rotate proxies, spoof browser fingerprints, or retry around
an explicit access block. A 401, 403, 429, CAPTCHA, login wall, malformed response, or
unexpected response shape stops the run and records evidence.

## Locally proven transport behavior

On 23 July 2026, plain Python `urllib` requests to Reddit JSON returned HTTP 403 from the
operator workstation. A normal headed Playwright browser context returned HTTP 200 and
valid Reddit `Listing` JSON for bounded requests to `smallbusiness`, `freelance`, and
`sysadmin`. The collector therefore uses the same browser-context request path while
retaining explicit stop safeguards.

## Required evidence from local smoke runs

Return the generated smoke package if any of these occur:

- no threads collected;
- invalid JSON or response-shape mismatch;
- block or CAPTCHA;
- login wall or rate limit;
- browser crash;
- report missing;
- trace missing.
