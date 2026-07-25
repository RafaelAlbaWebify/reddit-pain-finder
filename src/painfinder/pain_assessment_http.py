from __future__ import annotations

from painfinder.ai_review_http import ReviewerProfile
from painfinder.pain_assessment import (
    PainAssessment,
    PainAssessmentRequest,
    assessment_prompt_payload,
)
from painfinder.structured_ai_http import complete_structured


class HTTPPainAssessor:
    def __init__(self, profile: ReviewerProfile) -> None:
        self.profile = profile

    def assess(self, request: PainAssessmentRequest) -> PainAssessment:
        assessment = complete_structured(
            self.profile,
            schema_name="painfinder_pain_assessment",
            response_model=PainAssessment,
            user_prompt=assessment_prompt_payload(request),
        )
        return assessment.model_copy(
            update={"source_external_id": request.item.external_id}
        )
