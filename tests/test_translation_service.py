# ---------------------------------------------------------------------------
# translate_search_query cache (issue #77)
# ---------------------------------------------------------------------------


def _gemini_returning(monkeypatch, texts):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    model = MagicMock()
    model.generate_content.side_effect = [SimpleNamespace(text=t) for t in texts]
    monkeypatch.setattr("core.translation_service.GenerativeModel", lambda *_: model)
    return model


def test_translate_search_query_second_call_uses_cache(monkeypatch) -> None:
    from core.translation_service import translate_search_query

    model = _gemini_returning(monkeypatch, ["correr", "SHOULD-NOT-BE-USED"])
    assert translate_search_query("Run", "en", "es") == "correr"
    assert translate_search_query("run", "en", "es") == "correr"
    assert model.generate_content.call_count == 1


def test_translate_search_query_does_not_cache_none(monkeypatch) -> None:
    from core.translation_service import translate_search_query

    model = _gemini_returning(monkeypatch, ["", "correr"])
    assert translate_search_query("run", "en", "es") is None
    assert translate_search_query("run", "en", "es") == "correr"
    assert model.generate_content.call_count == 2
