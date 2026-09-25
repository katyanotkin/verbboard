"""Account deletion is self-service only: the signed-in button on the privacy page.

There is deliberately no request form or email path, so nobody can ask for someone
else's account to be deleted (the button only works for the signed-in owner).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_privacy_page_has_the_self_service_deletion_button_and_no_request_path(client: TestClient) -> None:
    html = client.get("/privacy").text
    assert 'id="data-deletion"' in html
    assert 'id="delete-account-btn"' in html
    assert "mailto:" not in html
    assert "deletion request" not in html.lower()
