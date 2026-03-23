from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from core.audio_service import ensure_audio
from core.lexicon import load_lexicon, index_by_id
from core.registry import get as get_plugin
from core.render import render_board_html
from core.paths import DATA_DIR
from core.tts import VOICES

router = APIRouter()


@router.get("/learn", response_class=HTMLResponse)
async def learn(
    request: Request,
    language: str = Query(...),
    verb_id: str | None = Query(None),
    voice: str | None = Query(None),
) -> HTMLResponse:
    lex_path = DATA_DIR / language / "lexicon.json"
    entries = load_lexicon(lex_path)
    by_id = index_by_id(entries)

    if not entries:
        return HTMLResponse("No verbs available", status_code=400)

    if language not in VOICES:
        return HTMLResponse("Unknown language voices", status_code=400)

    selected_voice = voice or "female"

    if selected_voice not in VOICES[language]:
        return HTMLResponse("Unknown voice", status_code=400)

    if not verb_id or verb_id not in by_id:
        verb_id = entries[0].id

    verb = by_id[verb_id]
    plugin = get_plugin(language)

    voice_meta = VOICES[language][selected_voice]
    board = plugin.build_board(verb, selected_voice, voice_meta.label)

    audio_backend = request.app.state.audio_backend
    tasks = []

    # Generate audio for board rows
    for section in board.sections:
        for row in section["rows"]:
            form_key = row["key"]
            text = str(row["text"] or "").strip()
            if not text:
                continue

            tasks.append(
                ensure_audio(
                    audio_backend=audio_backend,
                    text=text,
                    language=language,
                    verb_id=verb.id,
                    voice=selected_voice,
                    form_key=form_key,
                    voice_edge_id=voice_meta.edge_id,
                )
            )

    # Generate audio for examples
    for index, example in enumerate(board.verb.examples, start=1):
        example_text = example.dst.strip()
        if not example_text:
            continue

        tasks.append(
            ensure_audio(
                audio_backend=audio_backend,
                text=example_text,
                language=language,
                verb_id=verb.id,
                voice=selected_voice,
                form_key=f"example_{index}",
                voice_edge_id=voice_meta.edge_id,
            )
        )

    if tasks:
        await asyncio.gather(*tasks)

    html = render_board_html(board=board)
    return HTMLResponse(html)
