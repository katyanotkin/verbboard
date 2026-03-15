from __future__ import annotations

from html import escape

from core.models import Board
from core.paths import TEMPLATES_DIR


def render_board_html(board: Board) -> str:
    # lemma display
    lemma = board.verb.lemma
    if isinstance(lemma, dict):
        title = f"{lemma.get('imperfective','')} / {lemma.get('perfective','')}"
    else:
        title = str(lemma)

    sections_html = []
    for section in board.sections:
        rows = []
        for row in section["rows"]:
            key = row["key"]
            label = escape(str(row["label"]))
            text = escape(str(row["text"]))
            audio_src = (
                f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/{key}.mp3"
            )
            rows.append(
                "<tr>"
                f"<td>{label}</td>"
                f"<td style='font-size: 26px'>{text}</td>"
                f"<td>"
                f"<audio id='{key}' src='{audio_src}' preload='none'></audio>"
                f"<button onclick=\"document.getElementById('{key}').play()\">▶ Play</button>"
                f"</td>"
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
        examples_rows.append(
            "<tr>"
            f"<td>{escape(ex.dst)}</td>"
            f"<td>"
            f"<audio id='example_{index}' src='{audio_src}' preload='none'></audio>"
            f"<button onclick=\"document.getElementById('example_{index}').play()\">▶</button>"
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
