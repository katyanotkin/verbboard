---
name: translations-match-content
description: Use whenever you add, replace, regenerate or hand-edit any example sentence, lemma or other learner-visible text that has translations (verbs docs, examples, lemma_translations, i18n strings). Every translation must be updated to match the new text in every UI language, and checked on the rendered page.
---

# Translations always match the content

Owner rule (2026-11-04): after editing example sentences for `ru_davat`, the owner asked why the
translations were not updated and made "translations always match" a standing rule.

## Steps

1. When text with translations changes, replace its translations in the same write for EVERY UI language
   in `UI_LANGUAGES` except the verb's own language (today en, es, he for ru; check `core/languages/config.py`).
   Never leave an old translation next to a new sentence, and never drop the dict.
2. Re-derive everything that depends on the text: the example `target` (`tag_sentence` / `tag_from_hint`),
   audio is content-addressed (nothing to do), `lemma_translations` if the lemma changed.
3. Prefer the existing pipeline (`translate_examples`, `tools/backfill_translations.py`, admin regen)
   when credits and provider rules allow. For one-off hand edits, write the translations yourself and
   have them checked by the `linguist` agent for languages you are not sure of (he especially).
4. Verify on the rendered output, not only in Firestore: render the board for the verb with each
   `ui_language` (`core.render.render_board_html`) and confirm the new sentence and its translation
   appear together. Remember long-running instances cache entries for up to 300 s: say so when the
   owner will look at stage right after a data write.
5. i18n strings (`app/i18n/*.json`): all four locales change together, same meaning in each.
6. Final report lists, per changed item, the languages whose translation was updated.
