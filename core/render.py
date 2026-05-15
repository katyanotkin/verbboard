from __future__ import annotations

import json
from html import escape
from urllib.parse import quote

from core.audio_service import build_hashed_audio_key
from core.languages.config import LANGUAGE as LANG_CONFIG
from core.models import Board
from core.paths import TEMPLATES_DIR

NO_AUDIO_ROW_KEYS = {"aspect", "pair", "binyan", "root"}

_BOARD_TEMPLATE = (TEMPLATES_DIR / "board.html").read_text(encoding="utf-8")


def render_board_html(
    board: Board,
    return_to: str | None = None,
    candidate_verb_id: str | None = None,
    admin_href: str | None = None,
    ui_strings: dict[str, str] | None = None,
    ui_lang: str = "en",
) -> str:
    ui = ui_strings or {}
    html_dir = "rtl" if ui_lang == "he" else "ltr"

    lang_cfg = LANG_CONFIG.get(board.language)
    language_display = lang_cfg.native if lang_cfg else board.language.upper()

    lemma = board.verb.display_lemma or board.verb.lemma
    if isinstance(lemma, dict):
        title = f"{lemma.get('imperfective', '')} / {lemma.get('perfective', '')}"
    else:
        title = str(lemma)

    button_class = "btn"

    sections_html = []
    for section_index, section in enumerate(board.sections, start=1):
        rows = []
        for row_index, row in enumerate(section["rows"], start=1):
            key = str(row["key"])
            label = escape(str(row["label"]))
            raw_text = str(row["text"] or "")
            text = escape(raw_text)
            href = str(row.get("href", ""))

            if href:
                value_html = f"<a href='{escape(href)}'>{text}</a>"
            else:
                value_html = text

            if key not in NO_AUDIO_ROW_KEYS:
                hashed_key = build_hashed_audio_key(key, raw_text)
                audio_src = (
                    f"/audio/{board.language}/{board.verb.id}/"
                    f"{board.voice_key}/{hashed_key}.mp3"
                )
                audio_id = (
                    f"audio_{board.language}_{board.verb.id}_{board.voice_key}_"
                    f"section{section_index}_row{row_index}_{hashed_key}"
                )
                audio_html = (
                    f"<audio id='{audio_id}' src='{audio_src}' preload='none'></audio>"
                    f"<button class='{button_class}' data-lang='{board.language}' title='Play' "
                    f"onclick=\"const audio=document.getElementById('{audio_id}'); "
                    f'audio.pause(); audio.currentTime=0; audio.playbackRate=1.0; audio.play()">▶</button>'
                )
            else:
                audio_html = ""

            value_font_size = "15px" if key in ("pair", "aspect") else "22px"
            form_cell = (
                f"<span style='font-size:{value_font_size}'>{value_html}</span>"
                f"{audio_html}"
            )
            rows.append(
                "<tr>"
                f"<td class='conj-label'>{label}</td>"
                f"<td class='conj-form'>{form_cell}</td>"
                "</tr>"
            )
        col_label = escape(ui.get("board.col_label", "Label"))
        col_form = escape(ui.get("board.col_form", "Form"))

        section_title = section.get("title", "")
        title_html = f"<h2>{escape(str(section_title))}</h2>" if section_title else ""

        show_headers = bool(section_title)

        header_html = (
            f"<tr><th>{col_label}</th><th>{col_form}</th></tr>" if show_headers else ""
        )

        sections_html.append(
            title_html
            + "<table class='conj-table'>"
            + header_html
            + "".join(rows)
            + "</table>"
        )

    if len(sections_html) > 1:
        meta_section_html = sections_html[0]
        conj_sections_html = "".join(sections_html[1:])
    else:
        meta_section_html = ""
        conj_sections_html = "".join(sections_html)

    template = _BOARD_TEMPLATE

    translation_dir = "rtl" if ui_lang == "he" else "ltr"
    has_any_translation = any(
        ui_lang in ex.translations and board.language != ui_lang
        for ex in board.verb.examples
    )

    examples_rows = []
    for index, ex in enumerate(board.verb.examples, start=1):
        base_key = f"example_{index}"
        raw_text = ex.dst
        hashed_key = build_hashed_audio_key(base_key, raw_text)

        audio_src = (
            f"/audio/{board.language}/{board.verb.id}/"
            f"{board.voice_key}/{hashed_key}.mp3"
        )
        audio_id = (
            f"audio_{board.language}_{board.verb.id}_{board.voice_key}_{hashed_key}"
        )

        example_direction = "rtl" if board.language == "he" else "ltr"
        example_align = "right" if board.language == "he" else "left"

        translation_text = ""
        if board.language != ui_lang:
            translation_text = ex.translations.get(ui_lang, "")

        translation_span = (
            f"<span class='example-translation' dir='{translation_dir}'>"
            f"{escape(translation_text)}</span>"
        )

        examples_rows.append(
            "<tr>"
            f"<td dir='{example_direction}' style='text-align:{example_align}'>"
            f"<span class='example-src'>{escape(raw_text)}</span>"
            f"{translation_span}"
            f"</td>"
            f"<td>"
            f"<audio id='{audio_id}' src='{audio_src}' preload='none'></audio>"
            f"<button class='{button_class}' data-lang='{board.language}' title='Play' "
            f"onclick=\"const audio=document.getElementById('{audio_id}'); "
            f'audio.pause(); audio.currentTime=0; audio.playbackRate=1.0; audio.play()">▶</button>'
            f"<button class='slow-btn' title='Slow playback' "
            f"onclick=\"const audio=document.getElementById('{audio_id}'); "
            f'audio.pause(); audio.currentTime=0; audio.playbackRate=0.65; audio.play()">'
            f"<img src='/static/snail.svg' class='slow-icon' />"
            f"</button>"
            "</td>"
            "</tr>"
        )

    home_href = f"/?language={escape(board.language)}&verb_id={escape(board.verb.id)}"

    resolved_return_to = return_to or f"/?language={escape(board.language)}"

    source_suffix = "&source=candidate" if candidate_verb_id else ""
    learn_href = (
        f"/learn?language={escape(board.language)}"
        f"&verb_id={escape(board.verb.id)}{source_suffix}"
    )

    voice_key = (board.voice_key or "").lower()
    female_active = "active" if voice_key == "female" else ""
    male_active = "active" if voice_key == "male" else ""

    if candidate_verb_id:
        candidate_banner_assets = (
            '<link rel="stylesheet" href="/static/candidate_banner.css">'
            '<script defer src="/static/candidate_banner.js"></script>'
        )
        vid = escape(candidate_verb_id)
        admin = escape(admin_href or "/") + "#candidates"
        candidate_banner = f"""
<div class="candidate-banner" id="candidate-banner" data-admin-href="{admin}">
  <span class="candidate-banner-label">⚠ Candidate preview: <b>{escape(str(board.verb.lemma))}</b></span>
  <div class="candidate-banner-actions">
    <a href="{admin}" class="cand-nav-btn">← Admin</a>
    <button class="cand-btn-promote" onclick="candidateAction('{vid}', 'promote')">▲ Promote</button>
    <button class="cand-btn-fix" onclick="candidateAction('{vid}', 'fix')">⚑ Needs Fix</button>
    <button class="cand-btn-regen" onclick="candidateAction('{vid}', 'regen')">⟳ Regen</button>
  </div>
</div>"""
        voice_source_input = '<input type="hidden" name="source" value="candidate">'
    else:
        candidate_banner_assets = ""
        candidate_banner = ""
        voice_source_input = ""

    if has_any_translation:
        toggle_label_show = escape(
            ui.get("board.show_translations", "Show translations")
        )
        toggle_label_hide = escape(
            ui.get("board.hide_translations", "Hide translations")
        )
        examples_toggle = (
            f"<button id='toggle-translations' class='btn-secondary toggle-translations-btn' "
            f"data-label-show='{toggle_label_show}' "
            f"data-label-hide='{toggle_label_hide}'>"
            f"{toggle_label_show}</button>"
        )
    else:
        examples_toggle = ""

    board_ui_json = json.dumps(
        {
            "board.mark_known": ui.get("board.mark_known", "Mark as learned"),
            "board.known": ui.get("board.known", "Learned"),
            "practice.prev": ui.get("practice.prev", "Prev"),
            "practice.next": ui.get("practice.next", "Next"),
            "practice.of": ui.get("practice.of", "of"),
            "practice.finish": ui.get("practice.finish", "Finish"),
            "practice.abandon": ui.get("practice.abandon", "Abandon"),
            "practice.listen_first": ui.get(
                "practice.listen_first", "Listen to the audio first"
            ),
            "practice.wrap_up": ui.get("practice.wrap_up", "Practice complete"),
            "practice.learned_prompt": ui.get(
                "practice.learned_prompt", "Which verbs did you learn?"
            ),
            "practice.save": ui.get("practice.save", "Save"),
            "practice.skip": ui.get("practice.skip", "Skip"),
        },
        ensure_ascii=False,
    )

    html = (
        template.replace("{{title}}", escape(title))
        .replace("{{html_lang}}", ui_lang)
        .replace("{{html_dir}}", html_dir)
        .replace("{{candidate_banner_assets}}", candidate_banner_assets)
        .replace("{{candidate_banner}}", candidate_banner)
        .replace("{{voice_source_input}}", voice_source_input)
        .replace("{{language | urlencode}}", quote(board.language, safe=""))
        .replace("{{verb_id | urlencode}}", quote(board.verb.id, safe=""))
        .replace("{{return_to | urlencode}}", quote(resolved_return_to, safe="/"))
        .replace("{{learn_href | urlencode}}", quote(learn_href, safe="/"))
        .replace("{{language}}", escape(board.language))
        .replace("{{language_display}}", escape(language_display))
        .replace("{{voice_key}}", escape(board.voice_key))
        .replace("{{verb_id}}", escape(board.verb.id))
        .replace("{{home_href}}", home_href)
        .replace("{{return_to}}", escape(resolved_return_to))
        .replace("{{female_active}}", female_active)
        .replace("{{male_active}}", male_active)
        .replace("{{sections_meta}}", meta_section_html)
        .replace("{{sections_conj}}", conj_sections_html)
        .replace("{{examples}}", "".join(examples_rows))
        .replace("{{board_back}}", escape(ui.get("board.back", "Back")))
        .replace(
            "{{board_voice_female}}", escape(ui.get("board.voice_female", "Female"))
        )
        .replace("{{board_voice_male}}", escape(ui.get("board.voice_male", "Male")))
        .replace(
            "{{board_mark_known}}", escape(ui.get("board.mark_known", "Mark as known"))
        )
        .replace(
            "{{board_send_feedback}}",
            escape(ui.get("board.send_feedback", "Send feedback")),
        )
        .replace(
            "{{board_language_label}}",
            escape(ui.get("board.language_label", "Language:")),
        )
        .replace(
            "{{board_examples_heading}}",
            escape(ui.get("board.examples_heading", "Examples")),
        )
        .replace(
            "{{board_col_sentence}}", escape(ui.get("board.col_sentence", "Sentence"))
        )
        .replace("{{board_col_audio}}", escape(ui.get("board.col_audio", "Audio")))
        .replace("{{board_ui_json}}", board_ui_json)
        .replace("{{board_examples_toggle}}", examples_toggle)
    )

    return html
