from __future__ import annotations

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
    request_payload: dict[str, object] = {
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
        "messages": [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if profile.reasoning_effort is not None:
        request_payload["reasoning_effort"] = profile.reasoning_effort

    try:
        raw_response = _post_json(profile, _api_key(profile), request_payload)
        completion = ChatCompletionResponse.model_validate(raw_response)
        return response_model.model_validate_json(
            completion.choices[0].message.content
        )
    except (AIReviewRunnerError, ValidationError, ValueError) as error:
        raise StructuredAIHTTPError(
            f"Structured model {profile.name} returned an invalid response: {error}"
        ) from error


def _validate_remote_credentials(profile: ReviewerProfile) -> None:
    parsed = urllib.parse.urlparse(profile.endpoint)
    if profile.api_key_env is None and not _is_loopback_host(parsed.hostname):
        raise StructuredAIHTTPError(
            f"Structured model {profile.name} requires api_key_env "
            "for non-loopback endpoints"
        )
