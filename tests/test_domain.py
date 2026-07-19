import pytest
from pydantic import ValidationError

from painfinder.domain import ResearchRun


def test_live_collection_forces_single_concurrency() -> None:
    with pytest.raises(ValidationError):
        ResearchRun(name="unsafe", live_access_enabled=True, concurrency=2)


def test_default_policy_is_bounded_and_live_disabled() -> None:
    policy = ResearchRun(name="default")
    assert policy.max_pages == 25
    assert policy.max_threads == 10
    assert policy.live_access_enabled is False
