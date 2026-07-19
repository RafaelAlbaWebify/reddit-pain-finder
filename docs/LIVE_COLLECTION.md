# Live collection acceptance boundary

## Implemented

- headed Chromium persistent profile;
- old.reddit.com listing and thread adapters;
- bounded page, thread, comment, delay, concurrency, and runtime policies;
- approved-host enforcement;
- block, CAPTCHA, login-wall, and rate-limit stop detection;
- screenshot for every navigated page;
- Playwright trace for every run;
- selector-mismatch stop condition;
- generated HTML evidence report.

## Not yet proven

A live Reddit run has not been executed in this build environment. Reddit may block, redirect, or alter the old Reddit interface. The first local smoke run is therefore evidence gathering, not routine use.

## Required evidence from first local run

Return the entire `artifacts\live-smoke` directory if any of these occur:

- no threads collected;
- selector mismatch;
- block or CAPTCHA;
- login wall;
- browser crash;
- report missing;
- trace missing.
