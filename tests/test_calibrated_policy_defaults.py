from painfinder.pain_policy import PainPolicy


def test_default_policy_uses_calibrated_evidence_thresholds() -> None:
    policy = PainPolicy()

    assert policy.minimum_pain_confidence == 0.8
    assert policy.minimum_verification_confidence == 0.8
    assert policy.minimum_assessor_evidence_confidence == 0.7
    assert policy.minimum_verifier_evidence_confidence == 0.7
