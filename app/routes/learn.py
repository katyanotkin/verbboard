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
    verb_id: str = Query(...),
    voice: str = Query("female"),
) -> str:
    lex_path = DATA_DIR / language / "lexicon.json"
    entries = load_lexicon(lex_path)
    by_id = index_by_id(entries)

    if verb_id not in by_id:
        if entries:
            verb_id = entries[0].id
        else:
            return HTMLResponse("Unknown verb_id", status_code=400)

    if language not in VOICES:
        return HTMLResponse("Unknown language voices", status_code=400)

    if voice not in VOICES[language]:
        return HTMLResponse("Unknown voice", status_code=400)

    verb = by_id[verb_id]
    plugin = get_plugin(language)

    voice_meta = VOICES[language][voice]
    board = plugin.build_board(verb, voice, voice_meta.label)

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
                    voice=voice,
                    form_key=form_key,
                    voice_edge_id=voice_meta.edge_id,
                )
            )

    # Generate audio for examples
    for index, ex in enumerate(board.verb.examples, start=1):
        example_text = ex.dst.strip()
        if not example_text:
            continue

        tasks.append(
            ensure_audio(
                audio_backend=audio_backend,
                text=example_text,
                language=language,
                verb_id=verb.id,
                voice=voice,
                form_key=f"example_{index}",
                voice_edge_id=voice_meta.edge_id,
            )
        )

    # Run generation concurrently
    if tasks:
        await asyncio.gather(*tasks)

    return render_board_html(board)
