from __future__ import annotations

import urllib.error
import urllib.parse

from pydantic import BaseModel, ValidationError

from painfinder.ai_review_http import (
    AIReviewRunnerError,
    ChatCompletionResponse,
    ReviewerProfile,
    _api_key,
    _is_loopback_host,
    _post_json,
)


class StructuredAIHTTPError(RuntimeError):
    pass


def complete_structured[StructuredModel: BaseModel](
    profile: ReviewerProfile,
    *,
    schema_name: str,
    response_model: type[StructuredModel],
    user_prompt: str,
) -> StructuredModel:
    _validate_remote_credentials(profile)
    request_payload = _request_payload(
        profile,
        schema_name=schema_name,
        response_model=response_model,
        messages=[
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    try:
        content = _completion_content(profile, request_payload)
    except (AIReviewRunnerError, ValidationError, ValueError) as error:
        raise _structured_error(profile, error) from error

    try:
        return response_model.model_validate_json(content)
    except ValidationError as initial_error:
        repair_payload = _request_payload(
            profile,
            schema_name=schema_name,
            response_model=response_model,
            messages=[
                {"role": "system", "content": profile.system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": _repair_prompt(initial_error),
                },
            ],
        )
        try:
            repaired_content = _completion_content(profile, repair_payload)
            return response_model.model_validate_json(repaired_content)
        except (AIReviewRunnerError, ValidationError, ValueError) as repair_error:
            detail = _http_error_detail(repair_error)
            suffix = f"; server response: {detail}" if detail else ""
            raise StructuredAIHTTPError(
                f"Structured model {profile.name} returned an invalid response "
                f"after one semantic repair. Initial validation error: "
                f"{initial_error}. Repair error: {repair_error}{suffix}"
            ) from repair_error


def _request_payload[StructuredModel: BaseModel](
    profile: ReviewerProfile,
    *,
    schema_name: str,
    response_model: type[StructuredModel],
    messages: list[dict[str, str]],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": profile.model,
        "temperature": profile.temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": response_model.model_json_schema(),
            },
        },
        "messages": messages,
    }
    if profile.reasoning_effort is not None:
        payload["reasoning_effort"] = profile.reasoning_effort
    return payload


def _completion_content(
    profile: ReviewerProfile,
    request_payload: dict[str, object],
) -> str:
    raw_response = _post_json(profile, _api_key(profile), request_payload)
    completion = ChatCompletionResponse.model_validate(raw_response)
    return completion.choices[0].message.content


def _repair_prompt(error: ValidationError) -> str:
    return (
        "Repair the preceding JSON so it satisfies the same schema and all "
        "cross-field validation rules. Change only fields required to resolve "
        "the validation error. Do not add unsupported facts or evidence. Return "
        "exactly one corrected JSON object and no commentary. Validation error:\n"
        f"{error}"
    )


def _structured_error(
    profile: ReviewerProfile,
    error: BaseException,
) -> StructuredAIHTTPError:
    detail = _http_error_detail(error)
    suffix = f"; server response: {detail}" if detail else ""
    return StructuredAIHTTPError(
        f"Structured model {profile.name} returned an invalid response: {error}{suffix}"
    )


def _http_error_detail(error: BaseException) -> str | None:
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, urllib.error.HTTPError):
            try:
                body = cause.read().decode("utf-8", errors="replace").strip()
            except OSError:
                return None
            if not body:
                return None
            return body[:2000]
        cause = cause.__cause__
    return None


def _validate_remote_credentials(profile: ReviewerProfile) -> None:
    parsed = urllib.parse.urlparse(profile.endpoint)
    if profile.api_key_env is None and not _is_loopback_host(parsed.hostname):
        raise StructuredAIHTTPError(
            f"Structured model {profile.name} requires api_key_env "
            "for non-loopback endpoints"
        )
