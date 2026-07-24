from painfinder.analysis import detect_pain_signals
from painfinder.domain import SourceItem


def _item(external_id: str, text: str) -> SourceItem:
    return SourceItem.model_validate(
        {
            "external_id": external_id,
            "source_type": "post",
            "title": "",
            "body": text,
            "subreddit": "smallbusiness",
            "canonical_url": f"https://example.com/{external_id}",
        }
    )


def test_calibrated_patterns_cover_real_pain_families() -> None:
    items = [
        _item("status", "Do not make the client guess. Days have passed without updates."),
        _item("scope", "The last-minute change was not in the scope, so we switch to hourly."),
        _item("dark", "Multiple customers complained about dark mode, so we added a toggle."),
        _item("cash", "We are cash-poor because of overspending and failed budgeting."),
        _item("supplier", "The supplier printed it wrong and started production late."),
        _item("license", "The licensing system blocks growth; I want to operate independently."),
    ]

    detected = {signal.source_external_id for signal in detect_pain_signals(items)}

    assert detected == {"status", "scope", "dark", "cash", "supplier", "license"}


def test_calibrated_patterns_ignore_low_information_noise() -> None:
    items = [
        _item("thanks", "Thanks"),
        _item("congrats", "Congrats!"),
        _item("date", "7/23 is the date"),
        _item("discussion", "When do founders hire salespeople? What do you think?"),
    ]

    assert detect_pain_signals(items) == []
