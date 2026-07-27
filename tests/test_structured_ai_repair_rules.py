from painfinder.structured_ai_http import _schema_repair_rules


def test_assessor_repair_preserves_required_citations_or_abstains() -> None:
    rules = _schema_repair_rules("PainAssessment")

    assert "Preserve existing cited_signal_types and cited_evidence" in rules
    assert 'set verdict="abstain"' in rules
    assert 'Never return verdict="pain"' in rules
    assert "cited_signal_types, or cited_evidence" in rules
    assert "Do not fix one required field by deleting another required field" in rules
