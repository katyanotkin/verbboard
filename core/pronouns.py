from __future__ import annotations

# Personal-pronoun reference data (issue #32). Fixed, tiny, closed vocabulary
# that never changes -- a static table, not a Firestore/translate_lemma()
# concern. One entry per grammatical person, keyed identically across every
# language so a study-language word's "translation" is just the same-person
# lookup in PRONOUNS[ui_lang] -- no per-language-pair translation data needed.
#
# Covers both roles a language can play: study language (en/ru/he/es/it/fr,
# per core/registry.py's plugins) and UI language (en/ru/he/es, per
# core/languages/config.py's LANGUAGE dict). en/ru/he/es appear once and
# serve both roles.
PRONOUN_PERSONS: tuple[str, ...] = ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl")

PRONOUNS: dict[str, dict[str, str]] = {
    "en": {
        "1sg": "I",
        "2sg": "you",
        "3sg": "he / she / it",
        "1pl": "we",
        "2pl": "you",
        "3pl": "they",
    },
    "ru": {
        "1sg": "я",
        "2sg": "ты",
        "3sg": "он / она / оно",
        "1pl": "мы",
        "2pl": "вы",
        "3pl": "они",
    },
    "he": {
        "1sg": "אני",
        "2sg": "אתה / את",
        "3sg": "הוא / היא",
        "1pl": "אנחנו",
        "2pl": "אתם / אתן",
        "3pl": "הם / הן",
    },
    "es": {
        "1sg": "yo",
        "2sg": "tú",
        "3sg": "él / ella",
        "1pl": "nosotros / nosotras",
        # "vosotros" is Peninsular-only; most Spanish speakers (Latin America)
        # use "ustedes" for 2pl in every register -- see es/plugin.py's own
        # optional-vosotros handling and Ud./Uds. slots.
        "2pl": "vosotros / ustedes",
        "3pl": "ellos / ellas",
    },
    "it": {
        "1sg": "io",
        "2sg": "tu",
        # Lowercase "lei" = "she" here. Capitalized "Lei" (formal "you") is a
        # separate sense used for the imperative board row (see
        # core/languages/it/plugin.py) -- the two are unrelated by design;
        # do not resolve a "Lei" label against this table's "3sg" key.
        "3sg": "lui / lei",
        "1pl": "noi",
        "2pl": "voi",
        "3pl": "loro",
    },
    "fr": {
        "1sg": "je",
        "2sg": "tu",
        "3sg": "il / elle",
        "1pl": "nous",
        "2pl": "vous",
        "3pl": "ils / elles",
    },
}
