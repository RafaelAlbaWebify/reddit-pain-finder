from __future__ import annotations

from painfinder.ai_review_http import ReviewerProfile
from painfinder.pain_assessment import (
    PainAssessment,
    PainAssessmentRequest,
    assessment_prompt_payload,
)
from painfinder.structured_ai_http import complete_structured


_ASSESSMENT_OUTPUT_CONTRACT = "\n".join(
    (
        "Output contract:",
        (
            '- verdict="pain" requires at least one allowed category, a non-empty '
            "problem_statement, at least one cited_signal_type, and at least one "
            "cited_evidence span."
        ),
        (
            '- verdict="not_pain" or verdict="abstain" requires categories=[], '
            'problem_statement="", cited_signal_types=[], and cited_evidence=[].'
        ),
        '- Never return verdict="pain" with an empty categories array.',
    )
)


class HTTPPainAssessor:
    def __init__(self, profile: ReviewerProfile) -> None:
        self.profile = profile

    def assess(self, request: PainAssessmentRequest) -> PainAssessment:
        prompt = (
            f"{_ASSESSMENT_OUTPUT_CONTRACT}\n\n"
            f"{assessment_prompt_payload(request)}"
        )
        assessment = complete_structured(
            self.profile,
            schema_name="painfinder_pain_assessment",
            response_model=PainAssessment,
            user_prompt=prompt,
        )
        return assessment.model_copy(
            update={"source_external_id": request.item.external_id}
        )
