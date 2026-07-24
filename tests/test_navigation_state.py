from painfinder.browser_models import PageState
from painfinder.playwright_collector import resolve_navigation_state


def test_http_200_overrides_textual_block_false_positive() -> None:
    assert (
        resolve_navigation_state(
            status=200,
            detected_state=PageState.BLOCKED,
        )
        is PageState.NORMAL
    )


def test_http_403_remains_authoritative_block() -> None:
    assert (
        resolve_navigation_state(
            status=403,
            detected_state=PageState.NORMAL,
        )
        is PageState.BLOCKED
    )


def test_http_429_remains_rate_limited() -> None:
    assert (
        resolve_navigation_state(
            status=429,
            detected_state=PageState.NORMAL,
        )
        is PageState.RATE_LIMITED
    )


def test_captcha_on_http_200_is_preserved() -> None:
    assert (
        resolve_navigation_state(
            status=200,
            detected_state=PageState.CAPTCHA,
        )
        is PageState.CAPTCHA
    )
