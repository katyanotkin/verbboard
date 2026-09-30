import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.languages.ru.stress import strip_stress_marks


def _run(coroutine):
    # Playwright e2e tests can leave an asyncio loop running in the main thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def test_strips_marks_from_nested_payload_and_keeps_yo_and_short_i():
    payload = {
        "lemma": "выглядывать",
        "forms": {"present": {"1sg": "выгляды́ваю"}, "past": {"m": "всё́ пошёл"}},
        "examples": [{"dst": "Кот выгляды́вал из-под дивана.", "n": 3}],
        "morph": {"pair": "выглянуть"},
    }

    cleaned = strip_stress_marks(payload)

    assert cleaned["forms"]["present"]["1sg"] == "выглядываю"
    assert cleaned["forms"]["past"]["m"] == "всё пошёл"
    assert cleaned["examples"][0] == {"dst": "Кот выглядывал из-под дивана.", "n": 3}
    assert cleaned["morph"]["pair"] == "выглянуть"


def test_plain_text_is_returned_unchanged():
    assert strip_stress_marks("Она мыла окно. Й и й остаются.") == "Она мыла окно. Й и й остаются."


def test_non_russian_generation_is_not_stripped(monkeypatch):
    import json
    from types import SimpleNamespace

    from app.routes import admin_candidates

    payload = {"lemma": "gagner", "forms": {"x": "áb"}}

    class _Messages:
        async def create(self, **_kwargs):
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))])

    monkeypatch.setattr(admin_candidates, "get_anthropic_client", lambda: SimpleNamespace(messages=_Messages()))
    monkeypatch.setattr(admin_candidates, "get_cached_system", lambda _language: "")

    assert _run(admin_candidates._call_claude("fr", "gagner")) == payload
    assert _run(admin_candidates._call_claude("ru", "gagner"))["forms"]["x"] == "ab"


def test_autogen_claude_path_strips_only_russian(monkeypatch):
    import json
    from types import SimpleNamespace

    from core import verb_autogen

    payload = {"lemma": "x", "forms": {"a": "а́б"}}

    class _Messages:
        async def create(self, **_kwargs):
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))])

    monkeypatch.setattr(verb_autogen, "get_anthropic_client", lambda: SimpleNamespace(messages=_Messages()))
    monkeypatch.setattr(verb_autogen, "get_cached_system", lambda _language: "")

    assert _run(verb_autogen._generate_verb_claude("ru", "x"))["forms"]["a"] == "аб"
    assert _run(verb_autogen._generate_verb_claude("fr", "x")) == payload
