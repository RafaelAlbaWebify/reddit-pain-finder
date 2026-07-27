# Ruff repeatedly emits a no-op I001 fix for this valid import block.
# ruff: noqa: I001
from __future__ import annotations

from painfinder import pain_assessment
from painfinder.ai_review_http import ReviewerProfile
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

    def assess(
        self,
        request: pain_assessment.PainAssessmentRequest,
    ) -> pain_assessment.PainAssessment:
        prompt = (
            f"{_ASSESSMENT_OUTPUT_CONTRACT}\n\n"
            f"{pain_assessment.assessment_prompt_payload(request)}"
        )
        assessment = complete_structured(
            self.profile,
            schema_name="painfinder_pain_assessment",
            response_model=pain_assessment.PainAssessment,
            user_prompt=prompt,
        )
        return assessment.model_copy(
            update={"source_external_id": request.item.external_id}
        )
