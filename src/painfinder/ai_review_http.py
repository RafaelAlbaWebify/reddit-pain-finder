from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from painfinder.benchmark_review import REVIEW_COLUMNS
from painfinder.provisional_review import ReviewerDecision


class AIReviewRunnerError(RuntimeError):
    pass


class ReviewerProfile(BaseModel):
    name: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key_env: str | None = None
    system_prompt: str = Field(min_length=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=60.0, gt=0.0, le=300.0)
    retries: int = Field(default=2, ge=0, le=5)
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None

    @field_validator("endpoint")
    @classmethod
    def require_secure_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        parsed = urllib.parse.urlparse(normalized)
        if parsed.scheme == "https" and parsed.hostname:
            return normalized
        if parsed.scheme == "http" and _is_loopback_host(parsed.hostname):
            return normalized
        raise ValueError("endpoint must use https, except loopback HTTP is allowed")

    @field_validator("api_key_env")
    @classmethod
    def normalize_api_key_env(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ReviewRunnerConfig(BaseModel):
    reviewers: tuple[ReviewerProfile, ReviewerProfile, ReviewerProfile]


class ChatMessage(BaseModel):
    content: str


class ChatChoice(BaseModel):
    message: ChatMessage


class ChatCompletionResponse(BaseModel):
    choices: list[ChatChoice] = Field(min_length=1)


def run_http_ai_reviews(
    blind_packet: Path,
    config_path: Path,
    *,
    output_directory: Path,
) -> tuple[Path, Path, Path]:
    evidence = _load_blind_packet(blind_packet)
    config = _load_config(config_path)
    output_directory.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    temporary_paths: list[Path] = []
    try:
        for index, profile in enumerate(config.reviewers, start=1):
            output = output_directory / f"reviewer-{index}.jsonl"
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.unlink(missing_ok=True)
            decisions = [
                _review_item(profile, evidence[external_id]) for external_id in sorted(evidence)
            ]
            temporary.write_text(
                "".join(
                    json.dumps(decision.model_dump(mode="json"), separators=(",", ":")) + "\n"
                    for decision in decisions
                ),
                encoding="utf-8",
            )
            outputs.append(output)
            temporary_paths.append(temporary)

        for temporary, output in zip(temporary_paths, outputs, strict=True):
            temporary.replace(output)
    except Exception:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)
        raise

    return outputs[0], outputs[1], outputs[2]


def _load_config(path: Path) -> ReviewRunnerConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = ReviewRunnerConfig.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise AIReviewRunnerError(f"Invalid reviewer configuration: {error}") from error

    for profile in config.reviewers:
        parsed = urllib.parse.urlparse(profile.endpoint)
        if profile.api_key_env is None and not _is_loopback_host(parsed.hostname):
            raise AIReviewRunnerError(
                f"Reviewer {profile.name} requires api_key_env for non-loopback endpoints"
            )
    return config


def _load_blind_packet(path: Path) -> dict[str, dict[str, str]]:
    try:
        handle = path.open(encoding="utf-8-sig", newline="")
    except OSError as error:
        raise AIReviewRunnerError(f"Could not read blind packet: {error}") from error

    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REVIEW_COLUMNS:
            raise AIReviewRunnerError("Blind packet has unexpected columns")
        rows = list(reader)

    evidence: dict[str, dict[str, str]] = {}
    for line_number, row in enumerate(rows, start=2):
        normalized = {column: row.get(column) or "" for column in REVIEW_COLUMNS}
        external_id = normalized["external_id"].strip()
        if not external_id or external_id in evidence:
            raise AIReviewRunnerError(
                f"Invalid blind packet line {line_number}: IDs must be non-empty and unique"
            )
        evidence[external_id] = normalized
    if not evidence:
        raise AIReviewRunnerError("Blind packet is empty")
    return evidence


def _review_item(profile: ReviewerProfile, evidence: dict[str, str]) -> ReviewerDecision:
    api_key = _api_key(profile)
    request_payload: dict[str, Any] = {
        "model": profile.model,
        "temperature": profile.temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "painfinder_reviewer_decision",
                "strict": True,
                "schema": ReviewerDecision.model_json_schema(),
            },
        },
        "messages": [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": _evidence_prompt(evidence)},
        ],
    }
    if profile.reasoning_effort is not None:
        request_payload["reasoning_effort"] = profile.reasoning_effort

    raw_response = _post_json(profile, api_key, request_payload)
    try:
        completion = ChatCompletionResponse.model_validate(raw_response)
        decision = ReviewerDecision.model_validate_json(completion.choices[0].message.content)
    except (ValidationError, ValueError) as error:
        raise AIReviewRunnerError(
            f"Reviewer {profile.name} returned an invalid decision: {error}"
        ) from error

    expected_id = evidence["external_id"]
    if decision.external_id != expected_id:
        raise AIReviewRunnerError(
            f"Reviewer {profile.name} returned external_id {decision.external_id!r}; "
            f"expected {expected_id!r}"
        )
    return decision


def _api_key(profile: ReviewerProfile) -> str | None:
    if profile.api_key_env is None:
        return None
    api_key = os.environ.get(profile.api_key_env, "").strip()
    if not api_key:
        raise AIReviewRunnerError(
            f"Reviewer {profile.name} requires environment variable {profile.api_key_env}"
        )
    return api_key


def _post_json(
    profile: ReviewerProfile,
    api_key: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        profile.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    attempts = profile.retries + 1
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=profile.timeout_seconds,
            ) as response:
                body = response.read().decode("utf-8")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise AIReviewRunnerError(f"Reviewer {profile.name} returned a non-object response")
            return parsed
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt >= attempts:
                raise AIReviewRunnerError(
                    f"Reviewer {profile.name} request failed after {attempts} attempt(s): {error}"
                ) from error
            time.sleep(min(2 ** (attempt - 1), 4))
    raise AssertionError("unreachable")


def _is_loopback_host(hostname: str | None) -> bool:
    if hostname is None:
        return False
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _evidence_prompt(evidence: dict[str, str]) -> str:
    return json.dumps(
        {
            "task": (
                "Return one JSON object with external_id, expected_pain, "
                "expected_categories, expected_cluster, confidence, and rationale."
            ),
            "allowed_categories": [
                "manual_work",
                "explicit_demand",
                "workaround",
                "reliability",
                "cost",
            ],
            "evidence": {
                "external_id": evidence["external_id"],
                "source_type": evidence["source_type"],
                "title": evidence["title"],
                "body": evidence["body"],
                "community": evidence["community"],
                "canonical_url": evidence["canonical_url"],
            },
        },
        separators=(",", ":"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run three isolated OpenAI-compatible HTTP review profiles."
    )
    parser.add_argument("--blind-packet", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        outputs = run_http_ai_reviews(
            arguments.blind_packet,
            arguments.config,
            output_directory=arguments.output_directory,
        )
    except AIReviewRunnerError as error:
        print(f"ERROR: {error}")
        return 2
    print(f"PASS: wrote three isolated reviewer outputs to {arguments.output_directory}")
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
