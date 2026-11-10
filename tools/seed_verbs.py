"""One-off script: generate a curated list of common verbs for a study language
through the same pipeline a search miss uses (Claude generation -> example +
lemma translations -> live `verbs` doc + `verb_candidates` audit doc -> audio
pre-warm). Claude is used for every language here (the public search-miss path
uses Gemini for some languages; a hand-picked seed list is worth the better model).

Safe to re-run: a verb that already exists is skipped. The audio pre-warm writes to the
AUDIO_BUCKET in use (all environments share verbboard-audio-prod).

Usage:
    AUDIO_BUCKET=verbboard-audio-prod .venv/bin/python -m tools.seed_verbs --language tr
    AUDIO_BUCKET=verbboard-audio-prod .venv/bin/python -m tools.seed_verbs --language fr
    AUDIO_BUCKET=verbboard-audio-prod .venv/bin/python -m tools.seed_verbs --language es
    AUDIO_BUCKET=verbboard-audio-prod .venv/bin/python -m tools.seed_verbs --language pt
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.languages.es.plugin  # noqa: E402,F401  -- self-registers "es"
import core.languages.fr.plugin  # noqa: E402,F401  -- self-registers "fr"
import core.languages.it.plugin  # noqa: E402,F401  -- self-registers "it"
import core.languages.pt.plugin  # noqa: E402,F401  -- self-registers "pt"
import core.languages.tr.plugin  # noqa: E402,F401  -- self-registers "tr"
from core import verb_autogen  # noqa: E402
from core.audio_backend.factory import create_audio_backend  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.verb_repository import list_verbs  # noqa: E402

# Most common verbs by everyday frequency, in rank order. French: the 30 already
# live are the first ranks; these fill the gaps the linguist audit found (no
# impersonal falloir, which the prompt cannot represent without inventing forms).
LEMMAS: dict[str, list[str]] = {
    "tr": [
        "olmak",  # to be / become
        "yapmak",  # to do / make
        "etmek",  # to do (light verb)
        "gitmek",  # to go
        "gelmek",  # to come
        "görmek",  # to see
        "bilmek",  # to know
        "istemek",  # to want
        "vermek",  # to give
        "almak",  # to take / get
    ],
    "pt": [
        "ser",  # to be (permanent)
        "estar",  # to be (state)
        "ter",  # to have
        "ir",  # to go
        "fazer",  # to do / make
        "poder",  # can
        "querer",  # to want
        "saber",  # to know
        "dizer",  # to say
        "ver",  # to see
        "dar",  # to give
        "vir",  # to come
        "falar",  # regular -ar
        "comer",  # regular -er
        "partir",  # regular -ir
        "levantar-se",  # reflexive
        "trazer",  # irregular
        "pôr",  # irregular, circumflex
        "ler",  # to read
        "ouvir",  # to hear (eu ouço)
        "pedir",  # to ask for (eu peço)
        "dormir",  # stem change (eu durmo)
        "conhecer",  # eu conheço
        "começar",  # eu começo, c -> ç / qu
        "pagar",  # eu paguei
        "gostar",  # gostar de
        "precisar",  # precisar de
        "morar",  # to live (reside)
        "esperar",  # to wait / hope
        "chegar",  # eu cheguei
    ],
    "es": [
        "haber",
        "conocer",
        "parecer",
        "creer",
        "seguir",
        "volver",
        "llamarse",  # reflexive paradigm
        "quedar",
        "deber",
        "pedir",
        "sentir",
        "entender",
        "pasar",
        "recibir",
        "conseguir",
        "levantarse",  # reflexive paradigm
        "gustar",  # indirect-construction verb
    ],
    "it": [
        "mettere",
        "aspettare",
        "piacere",  # indirect-construction verb (mi piace)
        "chiamarsi",  # reflexive paradigm
        "alzarsi",
        "svegliarsi",
        "rimanere",
        "dormire",
        "decidere",
        "perdere",
    ],
    "fr": [
        "croire",
        "attendre",
        "comprendre",
        "partir",
        "écrire",
        "lire",
        "finir",  # regular -ir/-iss- verb
        "manger",  # nous mangeons
        "commencer",  # nous commençons
        "se lever",  # pronominal paradigm
    ],
}


async def main(language: str, provider: str) -> None:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)
    if provider == "claude":
        verb_autogen._CLAUDE_AUTOGEN_LANGUAGES = verb_autogen._CLAUDE_AUTOGEN_LANGUAGES | {language}
    print(f"Provider: {provider}")
    lemmas = LEMMAS[language]
    print(f"Generating {len(lemmas)} {language} verbs (audio bucket {settings.audio_bucket!r})...")

    for lemma in lemmas:
        print(f"  {lemma}...", flush=True)
        await verb_autogen.autogenerate_missing_verb(language=language, query=lemma, audio_backend=audio_backend)

    verbs = list_verbs(language)
    print(f"Done. {len(verbs)} {language} verbs live:")
    for verb in sorted(verbs, key=lambda item: item.get("rank") or 0):
        examples = verb.get("examples") or []
        translated = sum(1 for example in examples if example.get("translations"))
        print(
            f"  #{verb.get('rank')} {verb['verb_id']}: {len(examples)} examples "
            f"({translated} translated), lemma translations: {sorted((verb.get('lemma_translations') or {}))}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--language", required=True, choices=sorted(LEMMAS))
    parser.add_argument(
        "--provider",
        choices=("claude", "gemini"),
        default="claude",
        help="claude (default, Anthropic API) or gemini (Vertex AI gemini-2.5-flash, the search-miss provider for en/es/it/fr/pt)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.language, args.provider))
