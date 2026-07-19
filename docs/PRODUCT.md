# Product definition

## Purpose

Automatically inspect bounded, commercially relevant Reddit communities, identify recurring workflow problems, convert them into structured customer-pain hypotheses, and prepare the strongest candidates for deeper solution and competitor research.

## Initial user

A solo product researcher or founder operating the application locally.

## First useful workflow

1. Start a bounded discovery run.
2. Inspect collected source evidence.
3. Review candidate pains.
4. Reject false positives.
5. group similar pains.
6. select one pain for deeper validation.

## Non-goals for the first release

- crawling all of Reddit;
- posting or interacting with users;
- bypassing access controls;
- declaring ideas automatically validated;
- estimating market size from Reddit alone;
- cloud multi-user deployment;
- training models on Reddit content.

## Evidence standard

Each candidate pain must retain:

- original source URL;
- exact excerpt;
- collection timestamp;
- affected workflow where identifiable;
- detected pain category;
- confidence and detection reasons;
- independent-thread count once clustering exists;
- contradictory evidence once validation exists.
