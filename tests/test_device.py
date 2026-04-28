from __future__ import annotations

import pytest

from core.analytics.client_context import detect_device_type


@pytest.mark.parametrize(
    "user_agent, expected",
    [
        # Mobile
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148",
            "mobile",
        ),
        (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Mobile Safari/537.36",
            "mobile",
        ),
        # Tablet
        (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "tablet",
        ),
        ("Mozilla/5.0 (Linux; Android 13; SM-T870) tablet", "tablet"),
        # Desktop
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "desktop",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
            "desktop",
        ),
        # Unknown
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_detect_device_type(user_agent: str | None, expected: str) -> None:
    assert detect_device_type(user_agent) == expected


def test_mobile_wins_over_desktop_markers() -> None:
    # "mobile" keyword present alongside other markers — should be mobile
    ua = "SomeBot/1.0 Mobile android windows"
    assert detect_device_type(ua) == "mobile"
