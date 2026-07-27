from __future__ import annotations

from painfinder.pain_assessment_http import _ASSESSMENT_OUTPUT_CONTRACT


def test_assessment_output_contract_states_required_field_combinations() -> None:
    assert (
        'verdict="pain" requires at least one allowed category'
        in _ASSESSMENT_OUTPUT_CONTRACT
    )
    assert (
        'verdict="not_pain" or verdict="abstain" requires categories=[]'
        in _ASSESSMENT_OUTPUT_CONTRACT
    )
    assert (
        'Never return verdict="pain" with an empty categories array.'
        in _ASSESSMENT_OUTPUT_CONTRACT
    )
