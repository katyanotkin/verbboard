from __future__ import annotations


# Feedback open-redirect regression
def test_learn_feedback_link_encodes_return_to(page, live_server_url):
    page.goto(f"{live_server_url}/learn?language=en&verb_id=en_be&voice=female")
    page.wait_for_load_state("networkidle")

    link = page.locator("a.feedback-link").first
    href = link.get_attribute("href") or ""

    assert "page=learn" in href
    assert "language=en" in href
    assert "verb_id=en_be" in href
    assert "return_to=" in href
    assert "%3F" in href
    assert "%26" in href


# Learn feedback link preserves encoded return_to
def test_feedback_blocks_external_return_to(page, live_server_url):
    page.goto(
        f"{live_server_url}/feedback?return_to=https://malicious.example.com/path"
    )
    page.wait_for_load_state("networkidle")

    back = page.locator("a.secondary-link").first
    href = back.get_attribute("href") or ""

    assert "malicious.example.com" not in href
    assert href.startswith("/")
    assert "://" not in href


# Known star survives reload
def test_known_star_persists_after_reload(page, live_server_url):
    page.goto(f"{live_server_url}/learn?language=en&verb_id=en_be")
    page.wait_for_load_state("networkidle")

    star = page.locator("#known-btn")
    star.wait_for(state="visible")

    star.click()
    page.wait_for_timeout(300)
    assert star.get_attribute("aria-pressed") == "true"

    page.reload()
    page.wait_for_load_state("networkidle")

    star = page.locator("#known-btn")
    assert star.get_attribute("aria-pressed") == "true"
