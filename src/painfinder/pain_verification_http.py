from __future__ import annotations

from painfinder.ai_review_http import ReviewerProfile
from painfinder.pain_verification import (
    PainVerification,
    PainVerificationRequest,
    verification_prompt_payload,
)
from painfinder.structured_ai_http import complete_structured


class HTTPPainVerifier:
    def __init__(self, profile: ReviewerProfile) -> None:
        self.profile = profile

    def verify(self, request: PainVerificationRequest) -> PainVerification:
        verification = complete_structured(
            self.profile,
            schema_name="painfinder_pain_verification",
            response_model=PainVerification,
            user_prompt=verification_prompt_payload(request),
        )
        return verification.model_copy(
            update={"source_external_id": request.assessment.source_external_id}
        )
