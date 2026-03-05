from __future__ import annotations

from html import escape
from typing import Any, Dict

from core.models import Board


def render_board_html(board: Board) -> str:
    # lemma display
    lemma = board.verb.lemma
    if isinstance(lemma, dict):
        title = f"{lemma.get('imperfective','')} / {lemma.get('perfective','')}"
    else:
        title = str(lemma)

    examples_html = "".join(f"<li>{escape(ex.dst)}</li>" for ex in board.verb.examples)

    sections_html = []
    for section in board.sections:
        rows = []
        for row in section["rows"]:
            key = row["key"]
            label = escape(str(row["label"]))
            text = escape(str(row["text"]))
            audio_src = f"/audio/{board.language}/{board.verb.id}/{board.voice_key}/{key}.mp3"
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
            + "".join(rows) +
            "</table>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 980px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
    th {{ background: #f6f6f6; }}
    button {{ padding: 6px 10px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1 style="margin-bottom:6px;">{escape(title)}</h1>
  <div style="color:#555;margin-bottom:16px;">Language: <b>{escape(board.language)}</b> · Voice: <b>{escape(board.voice_label)}</b></div>

  <p><a href="/">Home</a></p>

  {''.join(sections_html)}

  <h2>Examples</h2>
  <ol>
    {examples_html}
  </ol>
</body>
</html>
"""
