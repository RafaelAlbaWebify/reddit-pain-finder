from pathlib import Path


def test_collector_uses_ephemeral_browser_context() -> None:
    source = Path("src/painfinder/playwright_collector.py").read_text(
        encoding="utf-8"
    )

    assert "launch_persistent_context" not in source
    assert "browser = await playwright.chromium.launch(headless=False)" in source
    assert "context = await browser.new_context(" in source
    assert 'locale="en-US"' in source
    assert "await browser.close()" in source
