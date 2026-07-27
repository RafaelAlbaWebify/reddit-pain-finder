# Ruff repeatedly emits a no-op I001 fix for this valid import block.
# ruff: noqa: I001
from __future__ import annotations

from painfinder import pain_verification
from painfinder.ai_review_http import ReviewerProfile
from painfinder.structured_ai_http import complete_structured


_VERIFICATION_OUTPUT_CONTRACT = "\n".join(
    (
        "Output contract:",
        (
            '- verdict="confirm" requires at least one confirmed category, '
            'reason="supported_by_source", and at least one cited_evidence span.'
        ),
        (
            '- verdict="reject" or verdict="abstain" requires '
            'confirmed_categories=[] and corrected_problem_statement="".'
        ),
        '- verdict="reject" must not include reason="supported_by_source".',
        (
            "- confirmed_categories must be selected only from the assessment "
            "categories; never invent a new category."
        ),
    )
)


class HTTPPainVerifier:
    def __init__(self, profile: ReviewerProfile) -> None:
        self.profile = profile

    def verify(
        self,
        request: pain_verification.PainVerificationRequest,
    ) -> pain_verification.PainVerification:
        prompt = (
            f"{_VERIFICATION_OUTPUT_CONTRACT}\n\n"
            f"{pain_verification.verification_prompt_payload(request)}"
        )
        verification = complete_structured(
            self.profile,
            schema_name="painfinder_pain_verification",
            response_model=pain_verification.PainVerification,
            user_prompt=prompt,
        )
        return verification.model_copy(
            update={"source_external_id": request.assessment.source_external_id}
        )
