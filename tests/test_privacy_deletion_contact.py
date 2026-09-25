"""Play requires a way to request account and data deletion; the privacy page carries
the button plus the feedback form (no scrapeable mailto:) for people who cannot sign in."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_privacy_page_offers_deletion_button_and_form_request(client: TestClient) -> None:
    html = client.get("/privacy").text
    assert 'id="data-deletion"' in html
    assert 'id="delete-account-btn"' in html
    assert "/feedback?page=privacy" in html
    assert "mailto:" not in html
