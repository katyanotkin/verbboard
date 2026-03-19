from __future__ import annotations

from html import escape

from core.models import Board
from core.paths import TEMPLATES_DIR

NO_AUDIO_ROW_KEYS = {"aspect", "pair"}


def render_board_html(board: Board) -> str:
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
            key = row["key"]
            label = escape(str(row["label"]))
            text = escape(str(row["text"]))
            href = str(row.get("href", ""))

            if href:
                value_html = f"<a href='{escape(href)}'>{text}</a>"
            else:
                value_html = text

            if key not in NO_AUDIO_ROW_KEYS:
                audio_src = f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/{key}.mp3"
                audio_id = (
                    f"audio_{board.language}_{board.verb.id}_{board.voice_key}_"
                    f"section{section_index}_row{row_index}_{key}"
                )
                audio_html = (
                    f"<audio id='{audio_id}' src='{audio_src}' preload='none'></audio>"
                    f"<button class='{button_class}' data-lang='{board.language}' title='Play' "
                    f"onclick=\"const audio=document.getElementById('{audio_id}'); "
                    f'audio.pause(); audio.currentTime=0; audio.playbackRate=1.0; audio.play()">▶</button>'
                )
            else:
                audio_html = ""

            rows.append(
                "<tr>"
                f"<td>{label}</td>"
                f"<td style='font-size: 26px'>{value_html}</td>"
                f"<td>{audio_html}</td>"
                "</tr>"
            )

        sections_html.append(
            f"<h2>{escape(section['title'])}</h2>"
            "<table>"
            "<tr><th>Label</th><th>Form</th><th>Audio</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    template = (TEMPLATES_DIR / "board.html").read_text(encoding="utf-8")

    examples_rows = []
    for index, ex in enumerate(board.verb.examples, start=1):
        audio_src = f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/example_{index}.mp3"
        audio_id = (
            f"audio_{board.language}_{board.verb.id}_{board.voice_key}_example_{index}"
        )

        example_direction = "rtl" if board.language == "he" else "ltr"
        example_align = "right" if board.language == "he" else "left"

        examples_rows.append(
            "<tr>"
            f"<td dir='{example_direction}' style='text-align:{example_align}'>{escape(ex.dst)}</td>"
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

    html = (
        template.replace("{{title}}", escape(title))
        .replace("{{language}}", escape(board.language))
        .replace("{{voice}}", escape(board.voice_label))
        .replace("{{sections}}", "".join(sections_html))
        .replace("{{examples}}", "".join(examples_rows))
    )

    return html
