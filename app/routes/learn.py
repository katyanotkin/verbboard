from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from core.cache import audio_path
from core.lexicon import load_lexicon, index_by_id
from core.registry import get as get_plugin
from core.render import render_board_html
from core.tts import VOICES, tts_to_mp3

router = APIRouter()


@router.get("/learn", response_class=HTMLResponse)
async def learn(
    language: str = Query(...),
    verb_id: str = Query(...),
    voice: str = Query("female"),
) -> str:
    lex_path = Path("data") / language / "lexicon.json"
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
    board = plugin.build_board(verb, voice_key=voice, voice_label=voice_meta.label)

    # Ensure audio is cached for all rows
    tasks = []
    for section in board.sections:
        for row in section["rows"]:
            form_key = row["key"]
            text = str(row["text"] or "").strip()
            if not text:
                continue
            out_path = audio_path(language, verb.id, voice, form_key)
            tasks.append(tts_to_mp3(text, out_path, voice_meta.edge_id))

    for index, ex in enumerate(board.verb.examples, start=1):
        example_text = ex.dst.strip()
        if not example_text:
            continue
        out_path = audio_path(language, verb.id, voice, f"example_{index}")
        tasks.append(tts_to_mp3(example_text, out_path, voice_meta.edge_id))

    # Generate with limited parallelism inside tts_to_mp3
    if tasks:
        await asyncio.gather(*tasks)

    return render_board_html(board)
