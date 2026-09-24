"""Tests for core/admin_feedback_service.py (issue #8).

Uses the shared in-memory Firestore fake (tests/fake_firestore.py, `fake_db`
fixture in conftest.py) -- this module previously had zero test coverage.

Covers:
- hide_feedback_by_id / unhide_feedback_by_id: missing-doc no-op, existing-doc
  flips only `hidden`
- list_feedback_rows: visibility/page/language/source/query filtering through
  the full Firestore-reading function, plus sort direction
- list_feedback_facets: sorted/deduped/empty-excluded pages/languages/sources
- _excluded_uids: short-circuits Firestore when no emails configured; queries
  `users` by email otherwise
- _read_sessions_summary: excluded uids dropped from every counter; date
  cutoff filtering; logged_in/verb_viewed truthiness gating
- _read_practice_summary: collection_group("languages") path filtering,
  empty-badges skip, per-uid dedup across language subcollections
- _read_users_summary: new/active-60d/active-7d cutoffs from real datetimes;
  excluded uids dropped from total
- get_active_poll_meta: current real core.polls config, plus the unset-poll
  short-circuit
- get_device_mix: composed integration shape across all three summaries
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import core.admin_feedback_service as admin_feedback_service


def _dt(days_ago: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days_ago)


def _date_str(days_ago: float) -> str:
    return _dt(days_ago).strftime("%Y-%m-%d")


# ── hide_feedback_by_id / unhide_feedback_by_id ─────────────────────────────


def test_hide_feedback_by_id_missing_doc_returns_false_and_writes_nothing(fake_db) -> None:
    before = fake_db.data
    assert admin_feedback_service.hide_feedback_by_id("does-not-exist") is False
    assert fake_db.data == before


def test_hide_feedback_by_id_flips_only_hidden(fake_db) -> None:
    fake_db.seed("feedback", {"fb1": {"comment": "hi", "page": "learn", "hidden": False}})

    assert admin_feedback_service.hide_feedback_by_id("fb1") is True

    doc = fake_db.data["feedback/fb1"]
    assert doc["hidden"] is True
    assert doc["comment"] == "hi"
    assert doc["page"] == "learn"


def test_unhide_feedback_by_id_missing_doc_returns_false_and_writes_nothing(fake_db) -> None:
    before = fake_db.data
    assert admin_feedback_service.unhide_feedback_by_id("does-not-exist") is False
    assert fake_db.data == before


def test_unhide_feedback_by_id_flips_only_hidden(fake_db) -> None:
    fake_db.seed("feedback", {"fb1": {"comment": "hi", "page": "learn", "hidden": True}})

    assert admin_feedback_service.unhide_feedback_by_id("fb1") is True

    doc = fake_db.data["feedback/fb1"]
    assert doc["hidden"] is False
    assert doc["comment"] == "hi"
    assert doc["page"] == "learn"


# ── list_feedback_rows ───────────────────────────────────────────────────────


def _seed_feedback_rows(fake_db) -> None:
    fake_db.seed(
        "feedback",
        {
            "fb1": {
                "hidden": False,
                "page": "learn",
                "language": "es",
                "source": "learn_page",
                "comment": "Great app",
                "created_at": _dt(4),
            },
            "fb2": {
                "hidden": True,
                "page": "learn",
                "language": "es",
                "source": "learn_page",
                "comment": "Bug found",
                "created_at": _dt(3),
            },
            "fb3": {
                "hidden": False,
                "page": "verbs",
                "language": "ru",
                "source": "verbs_page",
                "comment": "Add more verbs please",
                "created_at": _dt(2),
            },
            "fb4": {
                "hidden": False,
                "page": "learn",
                "language": "en",
                "source": "practice",
                "comment": "Love the practice loop",
                "created_at": _dt(1),
            },
            "fb5": {
                "hidden": False,
                "page": "learn",
                "language": "es",
                "source": "learn_page",
                "comment": "nothing special",
                "created_at": _dt(0),
            },
        },
    )


def _ids(rows: list[dict]) -> list[str]:
    return [row["id"] for row in rows]


def test_list_feedback_rows_visibility_hidden(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="hidden", page="", language="", source="", query="", limit=100
    )
    assert _ids(rows) == ["fb2"]


def test_list_feedback_rows_visibility_visible(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="visible", page="", language="", source="", query="", limit=100
    )
    assert set(_ids(rows)) == {"fb1", "fb3", "fb4", "fb5"}


def test_list_feedback_rows_visibility_all_includes_hidden(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="", language="", source="", query="", limit=100
    )
    assert set(_ids(rows)) == {"fb1", "fb2", "fb3", "fb4", "fb5"}


def test_list_feedback_rows_page_filter(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="learn", language="", source="", query="", limit=100
    )
    assert set(_ids(rows)) == {"fb1", "fb2", "fb4", "fb5"}


def test_list_feedback_rows_language_filter(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="", language="es", source="", query="", limit=100
    )
    assert set(_ids(rows)) == {"fb1", "fb2", "fb5"}


def test_list_feedback_rows_source_filter(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="", language="", source="practice", query="", limit=100
    )
    assert _ids(rows) == ["fb4"]


def test_list_feedback_rows_query_filter_is_case_insensitive(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="", language="", source="", query="VERB", limit=100
    )
    assert _ids(rows) == ["fb3"]


def test_list_feedback_rows_combined_filters(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="visible", page="learn", language="es", source="", query="", limit=100
    )
    # fb2 matches page/language but is hidden -> excluded by visibility="visible"
    assert set(_ids(rows)) == {"fb1", "fb5"}


def test_list_feedback_rows_sort_newest_is_descending(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="newest", visibility="all", page="", language="", source="", query="", limit=100
    )
    assert _ids(rows) == ["fb5", "fb4", "fb3", "fb2", "fb1"]


def test_list_feedback_rows_sort_oldest_is_ascending(fake_db) -> None:
    _seed_feedback_rows(fake_db)
    rows = admin_feedback_service.list_feedback_rows(
        sort="oldest", visibility="all", page="", language="", source="", query="", limit=100
    )
    assert _ids(rows) == ["fb1", "fb2", "fb3", "fb4", "fb5"]


# ── list_feedback_facets ─────────────────────────────────────────────────────


def test_list_feedback_facets_sorted_deduped_and_excludes_empty(fake_db) -> None:
    fake_db.seed(
        "feedback",
        {
            "fb1": {"page": "learn", "language": "es", "source": "learn_page", "created_at": _dt(3)},
            "fb2": {"page": "verbs", "language": "es", "source": "learn_page", "created_at": _dt(2)},
            "fb3": {"page": "learn", "language": "ru", "source": "verbs_page", "created_at": _dt(1)},
            # empty page/language/source must not appear in facets
            "fb4": {"page": "", "language": "", "source": "", "created_at": _dt(0)},
        },
    )

    facets = admin_feedback_service.list_feedback_facets()

    assert facets["pages"] == ["learn", "verbs"]
    assert facets["languages"] == ["es", "ru"]
    assert facets["sources"] == ["learn_page", "verbs_page"]


# ── _excluded_uids ────────────────────────────────────────────────────────────


def test_excluded_uids_empty_config_short_circuits_without_touching_firestore(monkeypatch, fake_db) -> None:
    monkeypatch.setattr(admin_feedback_service, "load_settings", lambda: SimpleNamespace(analytics_excluded_emails=()))

    def _boom():
        raise AssertionError("get_db must not be called when no excluded emails are configured")

    monkeypatch.setattr(admin_feedback_service, "get_db", _boom)

    assert admin_feedback_service._excluded_uids() == set()


def test_excluded_uids_queries_users_by_email(monkeypatch, fake_db) -> None:
    monkeypatch.setattr(
        admin_feedback_service,
        "load_settings",
        lambda: SimpleNamespace(analytics_excluded_emails=("owner@example.com", "tester@example.com")),
    )
    fake_db.seed(
        "users",
        {
            "uid_owner": {"email": "owner@example.com"},
            "uid_tester": {"email": "tester@example.com"},
            "uid_other": {"email": "someone-else@example.com"},
        },
    )

    assert admin_feedback_service._excluded_uids() == {"uid_owner", "uid_tester"}


# ── _read_sessions_summary ───────────────────────────────────────────────────


def test_read_sessions_summary_drops_excluded_uids_from_every_counter(fake_db) -> None:
    fake_db.seed(
        "analytics_sessions",
        {
            "s1": {
                "date": _date_str(5),
                "uid": "excluded_uid",
                "device_type": "mobile",
                "language": "es",
                "ui_lang": "en",
                "verb_viewed": True,
            },
            "s2": {
                "date": _date_str(5),
                "uid": "kept_uid",
                "device_type": "desktop",
                "language": "ru",
                "ui_lang": "ru",
                "verb_viewed": True,
            },
        },
    )

    summary = admin_feedback_service._read_sessions_summary(days=60, excluded_uids={"excluded_uid"})

    assert summary["total_sessions"] == 1
    assert summary["logged_in_sessions"] == 1
    assert summary["verb_viewed_sessions"] == 1
    assert summary["by_device"] == {"desktop": 1}
    assert summary["by_language"] == {"ru": 1}
    assert summary["by_ui_lang"] == {"ru": 1}


def test_read_sessions_summary_excludes_sessions_before_cutoff(fake_db) -> None:
    fake_db.seed(
        "analytics_sessions",
        {
            "in_window": {"date": _date_str(5), "device_type": "mobile", "language": "en", "ui_lang": "en"},
            "out_of_window": {"date": _date_str(90), "device_type": "mobile", "language": "en", "ui_lang": "en"},
        },
    )

    summary = admin_feedback_service._read_sessions_summary(days=60)

    assert summary["total_sessions"] == 1
    assert summary["by_device"] == {"mobile": 1}


def test_read_sessions_summary_logged_in_and_verb_viewed_require_truthy_fields(fake_db) -> None:
    fake_db.seed(
        "analytics_sessions",
        {
            "anon_no_view": {"date": _date_str(1), "uid": "", "verb_viewed": False},
            "anon_with_view": {"date": _date_str(1), "uid": "", "verb_viewed": True},
            "logged_in": {"date": _date_str(1), "uid": "u1", "verb_viewed": False},
        },
    )

    summary = admin_feedback_service._read_sessions_summary(days=60)

    assert summary["total_sessions"] == 3
    assert summary["logged_in_sessions"] == 1
    assert summary["verb_viewed_sessions"] == 1


# ── _read_practice_summary ───────────────────────────────────────────────────


def test_read_practice_summary_skips_docs_outside_user_practice(fake_db) -> None:
    fake_db.seed_path("not_practice/x/languages/en", {"badges": [1], "language": "en"})

    summary = admin_feedback_service._read_practice_summary()

    assert summary["practice_users_total"] == 0
    assert summary["practice_by_language"] == {}


def test_read_practice_summary_skips_empty_or_missing_badges(fake_db) -> None:
    fake_db.seed_path("user_practice/uid1/languages/en", {"badges": [], "language": "en"})
    fake_db.seed_path("user_practice/uid2/languages/en", {"language": "en"})  # no badges key at all

    summary = admin_feedback_service._read_practice_summary()

    assert summary["practice_users_total"] == 0
    assert summary["practice_by_language"] == {}


def test_read_practice_summary_dedupes_user_across_language_subcollections(fake_db) -> None:
    fake_db.seed_path("user_practice/uid1/languages/en", {"badges": [3], "language": "en"})
    fake_db.seed_path("user_practice/uid1/languages/ru", {"badges": [6], "language": "ru"})

    summary = admin_feedback_service._read_practice_summary()

    assert summary["practice_users_total"] == 1
    assert summary["practice_by_language"] == {"en": 1, "ru": 1}


def test_read_practice_summary_drops_excluded_uids(fake_db) -> None:
    fake_db.seed_path("user_practice/uid1/languages/en", {"badges": [3], "language": "en"})
    fake_db.seed_path("user_practice/uid2/languages/en", {"badges": [3], "language": "en"})

    summary = admin_feedback_service._read_practice_summary(excluded_uids={"uid1"})

    assert summary["practice_users_total"] == 1
    assert summary["practice_by_language"] == {"en": 1}


# ── _read_users_summary ──────────────────────────────────────────────────────


def test_read_users_summary_computes_cutoffs_from_real_datetimes(fake_db) -> None:
    fake_db.seed(
        "users",
        {
            # new (created 5d ago), active in both windows (updated 2d ago)
            "u_new_active": {"created_at": _dt(5), "updated_at": _dt(2)},
            # not new (created 100d ago), active in 60d window only (updated 10d ago)
            "u_old_active60": {"created_at": _dt(100), "updated_at": _dt(10)},
            # not new, not active in either window
            "u_dormant": {"created_at": _dt(200), "updated_at": _dt(200)},
        },
    )

    summary = admin_feedback_service._read_users_summary(days=60)

    assert summary["total"] == 3
    assert summary["new_last_60d"] == 1
    assert summary["active_last_60d"] == 2
    assert summary["active_last_7d"] == 1


def test_read_users_summary_drops_excluded_uids_from_total(fake_db) -> None:
    fake_db.seed(
        "users",
        {
            "kept": {"created_at": _dt(1), "updated_at": _dt(1)},
            "excluded": {"created_at": _dt(1), "updated_at": _dt(1)},
        },
    )

    summary = admin_feedback_service._read_users_summary(days=60, excluded_uids={"excluded"})

    assert summary["total"] == 1
    assert summary["new_last_60d"] == 1
    assert summary["active_last_60d"] == 1
    assert summary["active_last_7d"] == 1


# ── get_active_poll_meta ──────────────────────────────────────────────────────


def test_get_active_poll_meta_unset_returns_empty_dict(monkeypatch) -> None:
    monkeypatch.setattr(admin_feedback_service, "ACTIVE_POLL_ID", "")
    assert admin_feedback_service.get_active_poll_meta() == {}


def test_get_active_poll_meta_reflects_current_polls_config() -> None:
    """Documents current core.polls behavior: get_active_poll_meta() reads
    POLL_OPTIONS directly (not get_poll_options()), so it does NOT filter out
    POLL_HIDDEN_OPTIONS entries the way the public-facing poll rendering does.
    """
    from core.polls import ACTIVE_POLL_ID, POLL_OPTIONS, POLL_QUESTIONS

    meta = admin_feedback_service.get_active_poll_meta()

    assert meta["poll_id"] == ACTIVE_POLL_ID
    assert meta["question_en"] == POLL_QUESTIONS[ACTIVE_POLL_ID]["en"]
    expected_values = {value for value, _ in POLL_OPTIONS[ACTIVE_POLL_ID]}
    assert {option["value"] for option in meta["options"]} == expected_values
    # Hidden options (mobile_ux, more_verbs) are still present here, unlike
    # core.polls.get_poll_options() which filters them out for end users.
    assert "mobile_ux" in expected_values
    assert "mobile_ux" in {option["value"] for option in meta["options"]}


# ── get_device_mix (integration) ─────────────────────────────────────────────


def test_get_device_mix_composes_all_summaries(monkeypatch, fake_db) -> None:
    monkeypatch.setattr(admin_feedback_service, "load_settings", lambda: SimpleNamespace(analytics_excluded_emails=()))

    fake_db.seed(
        "analytics_sessions",
        {
            "s1": {
                "date": _date_str(1),
                "uid": "u1",
                "device_type": "mobile",
                "language": "es",
                "ui_lang": "en",
                "verb_viewed": True,
            },
            "s2": {
                "date": _date_str(1),
                "uid": "",
                "device_type": "desktop",
                "language": "ru",
                "ui_lang": "ru",
                "verb_viewed": False,
            },
        },
    )
    fake_db.seed("users", {"u1": {"created_at": _dt(5), "updated_at": _dt(10)}})
    fake_db.seed_path("user_practice/u1/languages/es", {"badges": [3], "language": "es"})

    result = admin_feedback_service.get_device_mix(days=60)

    assert result["days"] == 60
    assert result["total_sessions"] == 2
    assert result["logged_in_sessions"] == 1
    assert result["verb_viewed_sessions"] == 1
    assert result["by_device"] == {"mobile": 1, "desktop": 1}
    assert result["by_language"] == {"es": 1, "ru": 1}
    assert result["by_ui_lang"] == {"en": 1, "ru": 1}

    assert result["users"]["total"] == 1
    assert result["users"]["new_last_60d"] == 1
    assert result["users"]["active_last_60d"] == 1
    assert result["users"]["active_last_7d"] == 0

    assert result["practice"]["practice_users_total"] == 1
    assert result["practice"]["practice_by_language"] == {"es": 1}


# ── engagement flags and search hits ─────────────────────────────────────────


def test_read_sessions_summary_counts_engagement_flags(fake_db) -> None:
    fake_db.seed(
        "analytics_sessions",
        {
            "s1": {"date": _date_str(1), "home_viewed": True, "votd_clicked": True, "practice_started": True},
            "s2": {"date": _date_str(1), "home_viewed": True, "practice_started": True, "practice_completed": True},
            "s3": {"date": _date_str(1), "verb_viewed": True},
        },
    )

    summary = admin_feedback_service._read_sessions_summary(days=60)

    assert summary["engagement"] == {
        "home_viewed": 2,
        "votd_clicked": 1,
        "practice_started": 2,
        "practice_completed": 1,
    }


def test_read_search_hits_summary_splits_autogen_verbs(fake_db) -> None:
    fake_db.seed(
        "verb_candidates",
        {
            "ru_podderzhat": {"source": "autogen", "status": "promoted"},
            "ru_bezhat": {"source": "autogen", "status": "promoted"},
            "es_correr": {"source": None, "status": "promoted"},
            "ru_rejected": {"source": "autogen", "status": "rejected_non_verb"},
        },
    )
    fake_db.seed(
        "verb_search_hits",
        {
            "ru_ru_podderzhat": {"verb_id": "ru_podderzhat", "hits": 4},
            "es_es_correr": {"verb_id": "es_correr", "hits": 9},
        },
    )

    summary = admin_feedback_service._read_search_hits_summary()

    assert summary["autogen_verbs_total"] == 2
    assert summary["autogen_verbs_searched_again"] == 1
    assert summary["autogen_hits_total"] == 4
    assert [row["verb_id"] for row in summary["top"]] == ["es_correr", "ru_podderzhat"]
    assert summary["top"][1]["autogen"] is True
    assert summary["top"][0]["autogen"] is False


def test_read_search_hits_summary_empty(fake_db) -> None:
    assert admin_feedback_service._read_search_hits_summary() == {
        "autogen_verbs_total": 0,
        "autogen_verbs_searched_again": 0,
        "autogen_hits_total": 0,
        "top": [],
    }


def test_read_sessions_summary_counts_bots_separately(fake_db) -> None:
    fake_db.seed(
        "analytics_sessions",
        {
            "s1": {"date": _date_str(1), "device_type": "bot", "language": "es", "verb_viewed": True},
            "s2": {"date": _date_str(1), "device_type": "bot", "home_viewed": True},
            "s3": {"date": _date_str(1), "device_type": "mobile", "language": "ru", "home_viewed": True},
        },
    )

    summary = admin_feedback_service._read_sessions_summary(days=60)

    assert summary["bot_sessions"] == 2
    assert summary["total_sessions"] == 1
    assert summary["by_device"] == {"mobile": 1}
    assert summary["by_language"] == {"ru": 1}
    assert summary["verb_viewed_sessions"] == 0
    assert summary["engagement"]["home_viewed"] == 1
