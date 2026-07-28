from __future__ import annotations

import json
from html import escape
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.audio_service import build_hashed_audio_key
from core.languages.config import LANGUAGE as LANG_CONFIG
from core.models import Board
from core.paths import TEMPLATES_DIR
from core.safe_return import safe_return_to as _safe_return_to

NO_AUDIO_ROW_KEYS = {"aspect", "pair", "binyan", "root"}

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_board_html(
    board: Board,
    return_to: str | None = None,
    candidate_verb_id: str | None = None,
    admin_href: str | None = None,
    ui_strings: dict[str, str] | None = None,
    ui_lang: str = "en",
    firebase_web_config_json: str = "",
    translated_from: str | None = None,
    source_lang: str | None = None,
    streak_grace_enabled: bool = False,
    jump_to_example_enabled: bool = True,
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

    # When studying Hebrew with a non-Hebrew UI, label cells need explicit RTL
    # so Hebrew-script pronouns render correctly in a LTR page context.
    label_dir = ' dir="rtl"' if board.language == "he" and ui_lang != "he" else ""

    has_examples = bool(board.verb.examples)
    jump_title = escape(ui.get("board.jump_to_example", "Jump to example"))

    sections_html = []
    for section_index, section in enumerate(board.sections, start=1):
        rows = []
        for row_index, row in enumerate(section["rows"], start=1):
            key = str(row["key"])
            label = escape(str(row["label"]))
            raw_text = str(row["text"] or "")
            text = escape(raw_text)
            href = str(row.get("href", ""))
            is_conjugated_form = key not in NO_AUDIO_ROW_KEYS and bool(raw_text.strip())

            if href:
                value_html = f"<a href='{escape(href)}'>{text}</a>"
            else:
                value_html = text

            if key not in NO_AUDIO_ROW_KEYS:
                tts_key_text = str(row.get("tts_text") or "").strip() or raw_text
                hashed_key = build_hashed_audio_key(key, tts_key_text)
                audio_src = f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/{hashed_key}.mp3"
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
                if jump_to_example_enabled and has_examples and is_conjugated_form:
                    audio_html += (
                        f"<button type='button' class='jump-example-btn' title='{jump_title}' "
                        f'onclick="window.vbJumpToExample && vbJumpToExample(this)">🔎</button>'
                    )
            else:
                audio_html = ""

            value_font_size = "15px" if key in ("pair", "aspect") else "22px"
            form_cell = f"<span style='font-size:{value_font_size}'>{value_html}</span>{audio_html}"

            gender = str(row.get("gender", ""))
            number_val = str(row.get("number", ""))
            tr_attrs = ""
            if gender:
                tr_attrs += f" data-gender='{escape(gender)}'"
            if number_val:
                tr_attrs += f" data-number='{escape(number_val)}'"
            if is_conjugated_form:
                tr_attrs += f" data-form='{escape(raw_text)}'"

            rows.append(
                f"<tr{tr_attrs}>"
                f"<td class='conj-label'{label_dir}>{label}</td>"
                f"<td class='conj-form'>{form_cell}</td>"
                "</tr>"
            )
        col_label = escape(ui.get("board.col_label", "Label"))
        col_form = escape(ui.get("board.col_form", "Form"))

        section_title_raw = section.get("title", "")
        section_title = ui.get(section_title_raw, section_title_raw) if section_title_raw else ""
        title_html = f"<h2>{escape(str(section_title))}</h2>" if section_title else ""

        show_headers = bool(section_title)

        header_html = f"<tr><th>{col_label}</th><th>{col_form}</th></tr>" if show_headers else ""

        sections_html.append(title_html + "<table class='conj-table'>" + header_html + "".join(rows) + "</table>")

    if len(sections_html) > 1:
        meta_section_html = sections_html[0]
        conj_sections_html = "".join(sections_html[1:])
    else:
        meta_section_html = ""
        conj_sections_html = "".join(sections_html)

    translation_dir = "rtl" if ui_lang == "he" else "ltr"
    lemma_translation_text = ""
    if board.language != ui_lang:
        lemma_translation_text = board.verb.lemma_translations.get(ui_lang, "")
    lemma_translation_html = (
        f"<span class='lemma-translation' dir='{translation_dir}'>{escape(lemma_translation_text)}</span>"
    )
    has_any_translation = board.language != ui_lang and (
        any(ui_lang in ex.translations for ex in board.verb.examples) or bool(lemma_translation_text)
    )

    examples_rows = []
    for index, ex in enumerate(board.verb.examples, start=1):
        base_key = f"example_{index}"
        raw_text = ex.dst
        hashed_key = build_hashed_audio_key(base_key, raw_text)

        audio_src = f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/{hashed_key}.mp3"
        audio_id = f"audio_{board.language}_{board.verb.id}_{board.voice_key}_{hashed_key}"

        # dir and text-align on the sentence cell handle RTL languages correctly.
        # The audio cell is always the adjacent column -- the table layout keeps
        # them next to each other regardless of page/verb language direction.
        example_direction = "rtl" if board.language == "he" else "ltr"
        example_align = "right" if board.language == "he" else "left"

        translation_text = ""
        if board.language != ui_lang:
            translation_text = ex.translations.get(ui_lang, "")

        translation_span = (
            f"<span class='example-translation' dir='{translation_dir}'>{escape(translation_text)}</span>"
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

    ui_suffix = f"&ui_language={escape(ui_lang)}" if ui_lang else ""
    safe_rt = _safe_return_to(return_to) if return_to else None
    resolved_return_to = safe_rt or f"/?language={escape(board.language)}{ui_suffix}"

    source_suffix = "&source=candidate" if candidate_verb_id else ""
    learn_href = f"/learn?language={escape(board.language)}&verb_id={escape(board.verb.id)}{source_suffix}{ui_suffix}"
    # Include return_to so the feedback page's Back button returns here, not home.
    full_learn_href = learn_href + f"&return_to={quote(resolved_return_to, safe='')}"

    voice_key = (board.voice_key or "").lower()
    female_active = "active" if voice_key == "female" else ""
    male_active = "active" if voice_key == "male" else ""

    if translated_from and source_lang:
        lang_name = escape(ui.get(f"lang.{source_lang}", source_lang))
        tf_label = escape(ui.get("board.translated_from", "Found via"))
        translated_from_banner = (
            f'<div class="translated-from-banner" id="translated-from-banner">'
            f"<span>{tf_label} {lang_name}: <b>{escape(translated_from)}</b></span>"
            f'<button type="button" class="translated-from-dismiss" '
            f'onclick="this.parentElement.remove()" aria-label="Dismiss">×</button>'
            f"</div>"
        )
    else:
        translated_from_banner = ""

    if candidate_verb_id:
        candidate_banner_assets = (
            '<link rel="stylesheet" href="/static/candidate_banner.css">'
            '<script defer src="/static/candidate_banner.js"></script>'
        )
        vid = escape(candidate_verb_id)
        admin = escape(admin_href or "/admin#candidates")
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

    if translated_from:
        voice_source_input += f'<input type="hidden" name="translated_from" value="{escape(translated_from)}">'
    if source_lang:
        voice_source_input += f'<input type="hidden" name="source_lang" value="{escape(source_lang)}">'

    if has_any_translation:
        toggle_label_show = escape(ui.get("board.show_translations", "Show translations"))
        toggle_label_hide = escape(ui.get("board.hide_translations", "Hide translations"))
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
            "practice.skip": ui.get("practice.skip", "Skip"),
            "practice.abandon": ui.get("practice.abandon", "Abandon"),
            "practice.listen_first": ui.get("practice.listen_first", "Listen to the audio first"),
            "practice.wrap_up": ui.get("practice.wrap_up", "Practice complete"),
            "practice.learned_prompt": ui.get("practice.learned_prompt", "Which verbs did you learn?"),
            "practice.done": ui.get("practice.done", "Done"),
            "auth.login": ui.get("auth.login", "Login"),
            "auth.logout": ui.get("auth.logout", "Logout"),
            "board.no_example_for_form": ui.get("board.no_example_for_form", "No example yet for this form"),
        },
        ensure_ascii=False,
    )

    template = _jinja_env.get_template("board.html")
    return template.render(
        translated_from_banner=translated_from_banner,
        html_lang=ui_lang,
        html_dir=html_dir,
        title=title,
        lemma_translation=lemma_translation_html,
        candidate_banner_assets=candidate_banner_assets,
        board_ui_json=board_ui_json,
        firebase_web_config_json=firebase_web_config_json,
        streak_grace_enabled=streak_grace_enabled,
        candidate_banner=candidate_banner,
        language=board.language,
        verb_id=board.verb.id,
        language_display=language_display,
        board_language_label=ui.get("board.language_label", "Language:"),
        return_to=resolved_return_to,
        board_back=ui.get("board.back", "Back"),
        voice_source_input=voice_source_input,
        female_active=female_active,
        male_active=male_active,
        board_voice_label=ui.get("board.voice_label", "Audio voice"),
        board_voice_female=ui.get("board.voice_female", "Female"),
        board_voice_male=ui.get("board.voice_male", "Male"),
        board_mark_known=ui.get("board.mark_known", "Mark as learned"),
        board_send_feedback=ui.get("board.send_feedback", "Send feedback"),
        language_urlencode=quote(board.language, safe=""),
        verb_id_urlencode=quote(board.verb.id, safe=""),
        learn_href_urlencode=quote(full_learn_href, safe="/"),
        sections_meta=meta_section_html,
        board_examples_heading=ui.get("board.examples_heading", "Examples"),
        board_examples_toggle=examples_toggle,
        board_col_sentence=ui.get("board.col_sentence", "Sentence"),
        board_col_audio=ui.get("board.col_audio", "Audio"),
        examples="".join(examples_rows),
        sections_conj=conj_sections_html,
        show_gender_filter=board.language in {"he", "ru"},
        show_number_filter=board.language in {"he", "ru", "es"},
        board_filter_gender=ui.get("board.filter_gender", "Gender"),
        board_filter_number=ui.get("board.filter_number", "Number"),
        board_persona_all=ui.get("board.persona_all", "All"),
        board_persona_m=ui.get("board.persona_m", "M"),
        board_persona_f=ui.get("board.persona_f", "F"),
        board_number_sg=ui.get("board.number_sg", "Sg"),
        board_number_pl=ui.get("board.number_pl", "Pl"),
    )
