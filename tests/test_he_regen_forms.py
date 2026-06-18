"""
Tests for ללכת / הלך regen_forms flow -- Option A design.

Option A: forms field carries full nikud for both display and audio hashing.
tts_forms is a legacy field (written by old regen); regen_forms now clears it.

Covered:
  - build_hashed_audio_key: homograph forms get distinct keys via nikud in forms
  - Hebrew plugin (backward compat): tts_text still set on rows when tts_forms present
  - Hebrew plugin (Option A): row["text"] has nikud directly; no tts_text needed
  - render.py: audio src uses correct nikud hash in both old and new verb shapes
  - _warm_verb_audio: ensure_audio receives nikud text for key hashing
  - audio.py on-demand: resolves nikud key, sends nikud to TTS
  - POST /admin/api/verbs/{verb_id}/regen_forms: writes nikud forms, clears tts_forms
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.audio_backend.base import AudioBackend
from core.audio_service import build_hashed_audio_key
from core.models import Example, VerbEntry

# ---------------------------------------------------------------------------
# Shared nikud constants for הלך homograph forms
# past.2msg = "הָלַכְתָּ"  (qamatz + dagesh) -- halakhTA
# past.2fsg = "הָלַכְתְּ"  (shva)           -- halakhT
# ---------------------------------------------------------------------------

_PLAIN_2MSG = "הלכת"  # unvoweled -- same written form for both persons
_PLAIN_2FSG = "הלכת"

_NIKUD_2MSG = "הָלַכְתָּ"
_NIKUD_2FSG = "הָלַכְתְּ"

# ---------------------------------------------------------------------------
# Fixture A: LEGACY verb -- plain forms + separate tts_forms (pre-Option A)
# ---------------------------------------------------------------------------

_HE_FORMS_PLAIN = {
    "present": {"m_sg": "הולך", "f_sg": "הולכת", "m_pl": "הולכים", "f_pl": "הולכות"},
    "past": {
        "1sg": "הלכתי",
        "2msg": _PLAIN_2MSG,
        "2fsg": _PLAIN_2FSG,
        "3msg": "הלך",
        "3fsg": "הלכה",
        "1pl": "הלכנו",
        "2mpl": "הלכתם",
        "2fpl": "הלכתן",
        "3pl": "הלכו",
    },
    "future": {
        "1sg": "אלך",
        "2msg": "תלך",
        "2fsg": "תלכי",
        "3msg": "ילך",
        "3fsg": "תלך",
        "1pl": "נלך",
        "2mpl": "תלכו",
        "2fpl": "תלכנה",
        "3pl": "ילכו",
    },
    "imperative": {"ms": "לך", "fs": "לכי", "mp": "לכו", "fp": "לכנה"},
}

_HE_TTS_FORMS = {
    "past": {
        "1sg": "הָלַכְתִּי",
        "2msg": _NIKUD_2MSG,
        "2fsg": _NIKUD_2FSG,
        "3msg": "הָלַךְ",
        "3fsg": "הָלְכָה",
        "1pl": "הָלַכְנוּ",
        "2mpl": "הֲלַכְתֶּם",
        "2fpl": "הֲלַכְתֶּן",
        "3pl": "הָלְכוּ",
    },
}


def _make_he_verb_legacy() -> VerbEntry:
    """Old-style verb: plain forms + tts_forms with nikud."""
    return VerbEntry(
        id="he_llkt",
        rank=1,
        lemma="ללכת",
        forms=_HE_FORMS_PLAIN,
        tts_forms=_HE_TTS_FORMS,
        morph={"binyan": "פָּעַל", "root": "ה.ל.כ"},
        examples=[Example(dst="הוא הלך הביתה.")],
        display_lemma="ללכת",
    )


_HE_VERB_DATA_LEGACY = {
    "verb_id": "he_llkt",
    "language": "he",
    "lemma": "ללכת",
    "rank": 1,
    "forms": _HE_FORMS_PLAIN,
    "tts_forms": _HE_TTS_FORMS,
    "morph": {"binyan": "פָּעַל", "root": "ה.ל.כ"},
    "examples": [{"dst": "הוא הלך הביתה.", "translations": {}}],
    "tags": None,
    "display_lemma": "ללכת",
    "display_forms": None,
}

# ---------------------------------------------------------------------------
# Fixture B: OPTION A verb -- nikud in forms, no tts_forms
# ---------------------------------------------------------------------------

_HE_FORMS_NIKUD = {
    "present": {"m_sg": "הוֹלֵךְ", "f_sg": "הוֹלֶכֶת", "m_pl": "הוֹלְכִים", "f_pl": "הוֹלְכוֹת"},
    "past": {
        "1sg": "הָלַכְתִּי",
        "2msg": _NIKUD_2MSG,
        "2fsg": _NIKUD_2FSG,
        "3msg": "הָלַךְ",
        "3fsg": "הָלְכָה",
        "1pl": "הָלַכְנוּ",
        "2mpl": "הֲלַכְתֶּם",
        "2fpl": "הֲלַכְתֶּן",
        "3pl": "הָלְכוּ",
    },
    "future": {
        "1sg": "אֵלֵךְ",
        "2msg": "תֵּלֵךְ",
        "2fsg": "תֵּלְכִי",
        "3msg": "יֵלֵךְ",
        "3fsg": "תֵּלֵךְ",
        "1pl": "נֵלֵךְ",
        "2mpl": "תֵּלְכוּ",
        "2fpl": "תֵּלַכְנָה",
        "3pl": "יֵלְכוּ",
    },
    "imperative": {"ms": "לֵךְ", "fs": "לְכִי", "mp": "לְכוּ", "fp": "לֵכְנָה"},
}


def _make_he_verb_nikud() -> VerbEntry:
    """Option A verb: nikud in forms, no tts_forms."""
    return VerbEntry(
        id="he_llkt",
        rank=1,
        lemma="ללכת",
        forms=_HE_FORMS_NIKUD,
        tts_forms=None,
        morph={"binyan": "פָּעַל", "root": "ה.ל.כ"},
        examples=[Example(dst="הוא הלך הביתה.")],
        display_lemma="ללכת",
    )


_HE_VERB_DATA_NIKUD = {
    "verb_id": "he_llkt",
    "language": "he",
    "lemma": "ללכת",
    "rank": 1,
    "forms": _HE_FORMS_NIKUD,
    "tts_forms": None,
    "morph": {"binyan": "פָּעַל", "root": "ה.ל.כ"},
    "examples": [{"dst": "הוא הלך הביתה.", "translations": {}}],
    "tags": None,
    "display_lemma": "ללכת",
    "display_forms": None,
}


class _StubBackend(AudioBackend):
    def exists(self, key: str) -> bool:
        return False

    def read_bytes(self, key: str) -> bytes:
        return b"stub"

    def write_bytes(self, key: str, data: bytes) -> None:
        pass

    def list_keys(self, prefix: str):
        return iter([])


def _run_async(coro) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, coro).result()


def _admin_cookies() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


# ---------------------------------------------------------------------------
# 1. Key computation: homograph forms get distinct keys via nikud
# ---------------------------------------------------------------------------


def test_plain_homograph_forms_have_same_written_text() -> None:
    assert _PLAIN_2MSG == _PLAIN_2FSG


def test_nikud_forms_differ_for_homograph_forms() -> None:
    assert _NIKUD_2MSG != _NIKUD_2FSG


def test_nikud_based_keys_are_distinct_for_homograph_forms() -> None:
    key_2msg = build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    key_2fsg = build_hashed_audio_key("past_2fsg", _NIKUD_2FSG)
    assert key_2msg != key_2fsg


def test_nikud_key_differs_from_plain_key() -> None:
    """Switching from plain to nikud text must produce a different GCS path."""
    plain_key = build_hashed_audio_key("past_2msg", _PLAIN_2MSG)
    nikud_key = build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    assert plain_key != nikud_key


# ---------------------------------------------------------------------------
# 2a. Hebrew plugin (backward compat): tts_text set on rows when tts_forms present
# ---------------------------------------------------------------------------


def test_legacy_board_past_rows_have_tts_text() -> None:
    from core.languages.he.plugin import build_board
    from core.tts import VOICES

    verb = _make_he_verb_legacy()
    board = build_board(verb, "female", VOICES["he"]["female"].label)

    past = next(s for s in board.sections if s.get("title") == "board.tense_past")
    rows = {str(r["key"]): r for r in past["rows"]}

    assert rows["past_2msg"].get("tts_text") == _NIKUD_2MSG
    assert rows["past_2fsg"].get("tts_text") == _NIKUD_2FSG


def test_legacy_board_display_text_is_plain() -> None:
    from core.languages.he.plugin import build_board
    from core.tts import VOICES

    verb = _make_he_verb_legacy()
    board = build_board(verb, "female", VOICES["he"]["female"].label)

    past = next(s for s in board.sections if s.get("title") == "board.tense_past")
    rows = {str(r["key"]): r for r in past["rows"]}

    assert rows["past_2msg"]["text"] == _PLAIN_2MSG
    assert rows["past_2fsg"]["text"] == _PLAIN_2FSG


# ---------------------------------------------------------------------------
# 2b. Hebrew plugin (Option A): nikud in forms, no tts_forms
#     row["text"] carries nikud directly; tts_text not needed
# ---------------------------------------------------------------------------


def test_option_a_board_rows_display_nikud_from_forms() -> None:
    from core.languages.he.plugin import build_board
    from core.tts import VOICES

    verb = _make_he_verb_nikud()
    board = build_board(verb, "female", VOICES["he"]["female"].label)

    past = next(s for s in board.sections if s.get("title") == "board.tense_past")
    rows = {str(r["key"]): r for r in past["rows"]}

    assert rows["past_2msg"]["text"] == _NIKUD_2MSG
    assert rows["past_2fsg"]["text"] == _NIKUD_2FSG


def test_option_a_board_rows_have_no_tts_text() -> None:
    """When forms carry nikud and tts_forms is absent, tts_text is not set."""
    from core.languages.he.plugin import build_board
    from core.tts import VOICES

    verb = _make_he_verb_nikud()
    board = build_board(verb, "female", VOICES["he"]["female"].label)

    past = next(s for s in board.sections if s.get("title") == "board.tense_past")
    rows = {str(r["key"]): r for r in past["rows"]}

    assert "tts_text" not in rows["past_2msg"]
    assert "tts_text" not in rows["past_2fsg"]


# ---------------------------------------------------------------------------
# 3. render.py: audio src uses nikud hash in both old and new verb shapes
# ---------------------------------------------------------------------------


def test_render_legacy_audio_src_uses_tts_text_hash() -> None:
    """Legacy verb: audio src in HTML must use the tts_text (nikud) hash."""
    from core.languages.he.plugin import build_board
    from core.render import render_board_html
    from core.tts import VOICES

    verb = _make_he_verb_legacy()
    board = build_board(verb, "female", VOICES["he"]["female"].label)
    html = render_board_html(board, ui_lang="en")

    expected_2msg = build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    expected_2fsg = build_hashed_audio_key("past_2fsg", _NIKUD_2FSG)
    stale_plain = build_hashed_audio_key("past_2msg", _PLAIN_2MSG)

    assert expected_2msg in html
    assert expected_2fsg in html
    assert stale_plain not in html, "plain-text hash must not appear when tts_text is set"


def test_render_option_a_audio_src_uses_nikud_forms_hash() -> None:
    """Option A verb: audio src must use nikud directly from forms."""
    from core.languages.he.plugin import build_board
    from core.render import render_board_html
    from core.tts import VOICES

    verb = _make_he_verb_nikud()
    board = build_board(verb, "female", VOICES["he"]["female"].label)
    html = render_board_html(board, ui_lang="en")

    expected_2msg = build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    expected_2fsg = build_hashed_audio_key("past_2fsg", _NIKUD_2FSG)

    assert expected_2msg in html
    assert expected_2fsg in html
    assert _NIKUD_2MSG in html, "nikud text must be visible in the rendered cell"


# ---------------------------------------------------------------------------
# 4. _warm_verb_audio: ensure_audio receives nikud text
# ---------------------------------------------------------------------------


def test_warm_legacy_uses_tts_text_for_form_key(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    calls: list[dict] = []

    async def _capture(**kwargs):
        calls.append({"form_key": kwargs["form_key"], "text": kwargs["text"]})

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)
    _run_async(_warm_verb_audio(_StubBackend(), "he", _HE_VERB_DATA_LEGACY))

    keys_by_text = {c["text"]: c["form_key"] for c in calls}

    assert keys_by_text.get(_NIKUD_2MSG) == build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    assert keys_by_text.get(_NIKUD_2FSG) == build_hashed_audio_key("past_2fsg", _NIKUD_2FSG)


def test_warm_option_a_uses_nikud_forms_for_form_key(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    calls: list[dict] = []

    async def _capture(**kwargs):
        calls.append({"form_key": kwargs["form_key"], "text": kwargs["text"]})

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)
    _run_async(_warm_verb_audio(_StubBackend(), "he", _HE_VERB_DATA_NIKUD))

    keys_by_text = {c["text"]: c["form_key"] for c in calls}

    assert keys_by_text.get(_NIKUD_2MSG) == build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    assert keys_by_text.get(_NIKUD_2FSG) == build_hashed_audio_key("past_2fsg", _NIKUD_2FSG)


def test_warm_homograph_forms_get_distinct_form_keys(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    form_keys: list[str] = []

    async def _capture(**kwargs):
        if kwargs["text"] in (_NIKUD_2MSG, _NIKUD_2FSG):
            form_keys.append(kwargs["form_key"])

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)
    _run_async(_warm_verb_audio(_StubBackend(), "he", _HE_VERB_DATA_NIKUD))

    assert len(form_keys) == 4, "both homograph forms × 2 voices"
    assert len(set(form_keys)) == 2, "form_keys must differ between the two persons"


# ---------------------------------------------------------------------------
# 5. audio.py on-demand: resolves nikud key, sends nikud to TTS
# ---------------------------------------------------------------------------


def test_audio_route_resolves_nikud_key(client: TestClient, monkeypatch) -> None:
    """GET /audio with nikud-based key must find the row and send nikud to TTS."""
    called_with: list[dict] = []

    async def _capture(**kwargs):
        called_with.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _capture)
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: _make_he_verb_nikud())

    form_key = build_hashed_audio_key("past_2msg", _NIKUD_2MSG)
    resp = client.get(f"/audio/he/he_llkt/female/{form_key}.mp3")

    assert resp.status_code == 200
    assert len(called_with) == 1
    assert called_with[0]["text"] == _NIKUD_2MSG
    assert called_with[0]["form_key"] == form_key


def test_audio_route_plain_key_returns_404_for_nikud_verb(client: TestClient, monkeypatch) -> None:
    """A plain-text-based key must 404 for an Option A verb -- URL is stale."""

    async def _noop(**kwargs):
        pass

    monkeypatch.setattr("app.routes.audio.ensure_audio", _noop)
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: _make_he_verb_nikud())

    old_key = build_hashed_audio_key("past_2msg", _PLAIN_2MSG)
    resp = client.get(f"/audio/he/he_llkt/female/{old_key}.mp3")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. POST /admin/api/verbs/{verb_id}/regen_forms endpoint
# ---------------------------------------------------------------------------


def _mock_live_verb_db(verb_id: str, data: dict | None) -> MagicMock:
    mock_doc = MagicMock()
    mock_doc.exists = data is not None
    mock_doc.to_dict.return_value = data or {}

    mock_ref = MagicMock()
    mock_ref.get.return_value = mock_doc
    mock_ref.update = MagicMock()

    mock_col = MagicMock()
    mock_col.document.return_value = mock_ref

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_col
    return mock_db


_LIVE_VERB = {
    "verb_id": "he_llkt",
    "language": "he",
    "lemma": "ללכת",
    "rank": 5,
    "forms": {"past": {"2msg": _PLAIN_2MSG, "2fsg": _PLAIN_2FSG}},
    "tts_forms": _HE_TTS_FORMS,  # legacy field present before regen
    "morph": {"binyan": "פָּעַל", "root": "ה.ל.כ"},
    "examples": [{"dst": "הוא הלך הביתה."}],
}

# Claude response under Option A: nikud in forms, no tts_forms
_CLAUDE_RESPONSE = {
    "lemma": "ללכת",
    "morph": {"binyan": "פָּעַל", "root": "ה.ל.כ"},
    "forms": _HE_FORMS_NIKUD,
    "examples": [],
}


def test_regen_forms_happy_path(client: TestClient) -> None:
    db = _mock_live_verb_db("he_llkt", _LIVE_VERB)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=_CLAUDE_RESPONSE)),
        patch("app.routes.admin_candidates._warm_verb_audio", new=AsyncMock()),
    ):
        resp = client.post("/admin/api/verbs/he_llkt/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 200
    body = resp.json()
    assert body["verb_id"] == "he_llkt"
    assert body["regenerated"] is True
    assert "updated_at" in body


def test_regen_forms_writes_nikud_forms_and_clears_tts_forms(client: TestClient) -> None:
    """regen_forms must write nikud in forms and explicitly clear legacy tts_forms."""
    db = _mock_live_verb_db("he_llkt", _LIVE_VERB)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=_CLAUDE_RESPONSE)),
        patch("app.routes.admin_candidates._warm_verb_audio", new=AsyncMock()),
    ):
        resp = client.post("/admin/api/verbs/he_llkt/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 200
    update_call = db.collection.return_value.document.return_value.update
    update_call.assert_called_once()
    written = update_call.call_args[0][0]

    assert written["forms"] == _HE_FORMS_NIKUD, "forms must carry nikud"
    assert written["tts_forms"] is None, "legacy tts_forms must be cleared"
    assert written["forms"]["past"]["2msg"] == _NIKUD_2MSG
    assert written["forms"]["past"]["2fsg"] == _NIKUD_2FSG


def test_regen_forms_keeps_existing_examples(client: TestClient) -> None:
    db = _mock_live_verb_db("he_llkt", _LIVE_VERB)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=_CLAUDE_RESPONSE)),
        patch("app.routes.admin_candidates._warm_verb_audio", new=AsyncMock()),
    ):
        client.post("/admin/api/verbs/he_llkt/regen_forms", cookies=_admin_cookies())

    written = db.collection.return_value.document.return_value.update.call_args[0][0]
    assert "examples" not in written, "regen_forms must not overwrite examples"


def test_regen_forms_verb_not_found(client: TestClient) -> None:
    db = _mock_live_verb_db("he_missing", None)

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post("/admin/api/verbs/he_missing/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 404


def test_regen_forms_missing_lemma_returns_422(client: TestClient) -> None:
    db = _mock_live_verb_db("he_llkt", {**_LIVE_VERB, "lemma": ""})

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post("/admin/api/verbs/he_llkt/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 422


def test_regen_forms_requires_auth(client: TestClient) -> None:
    resp = client.post("/admin/api/verbs/he_llkt/regen_forms")
    assert resp.status_code == 401
