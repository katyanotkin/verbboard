from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse

from core.audio_service import (
    build_hashed_audio_key,
    ensure_audio,
    prewarm_verb_audio_keys,
)
from core.i18n import get_strings, resolve_ui_language
from core.registry import get as get_plugin
from core.render import render_board_html
from core.tts import VOICES
from core.verb_loader import load_entries_for_language, load_entry_by_id

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_audio_background(audio_backend, language, verb_id, voice, tasks) -> None:
    await prewarm_verb_audio_keys(audio_backend, language, verb_id, voice)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Audio generation failed: %s", result)


@router.get("/learn", response_class=HTMLResponse)
async def learn(
    request: Request,
    background_tasks: BackgroundTasks,
    language: str = Query(...),
    verb_id: str | None = Query(None),
    voice: str | None = Query(None),
    source: str | None = Query(None),
    return_to: str | None = Query(None),
) -> HTMLResponse:
    logger.debug("lookup source %s -> verb %s", source, verb_id)
    if source == "candidate":
        if not verb_id:
            return HTMLResponse(
                "verb_id required for candidate preview", status_code=400
            )
        verb = load_entry_by_id(
            language=language,
            verb_id=verb_id,
            source="candidate",
        )
        logger.debug("Candidate lookup %s -> %s", verb_id, verb)
        if verb is None:
            return HTMLResponse("Candidate not found", status_code=404)
    else:
        if verb_id:
            verb = load_entry_by_id(language=language, verb_id=verb_id)
            if verb is None:
                return HTMLResponse("Verb not found", status_code=404)
        else:
            entries = load_entries_for_language(language=language)
            if not entries:
                return HTMLResponse("No verbs available", status_code=400)
            verb = entries[0]

    if language not in VOICES:
        return HTMLResponse("Unknown language voices", status_code=400)

    selected_voice = voice or "female"

    if selected_voice not in VOICES[language]:
        return HTMLResponse("Unknown voice", status_code=400)

    plugin = get_plugin(language)

    voice_meta = VOICES[language][selected_voice]
    board = plugin.build_board(verb, selected_voice, voice_meta.label)

    audio_backend = request.app.state.audio_backend
    tasks = []

    for section in board.sections:
        for row in section["rows"]:
            base_form_key = str(row["key"])
            text = str(row["text"] or "").strip()
            if not text:
                continue

            form_key = build_hashed_audio_key(base_form_key, text)

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

    for index, example in enumerate(board.verb.examples, start=1):
        example_text = example.dst.strip()
        if not example_text:
            continue

        base_form_key = f"example_{index}"
        form_key = build_hashed_audio_key(base_form_key, example_text)

        tasks.append(
            ensure_audio(
                audio_backend=audio_backend,
                text=example_text,
                language=language,
                verb_id=verb.id,
                voice=selected_voice,
                form_key=form_key,
                voice_edge_id=voice_meta.edge_id,
            )
        )

    if tasks:
        background_tasks.add_task(
            _run_audio_background,
            audio_backend,
            language,
            verb.id,
            selected_voice,
            tasks,
        )

    ui_lang = resolve_ui_language(request)
    ui_strings = get_strings(ui_lang)

    html = render_board_html(
        board=board,
        return_to=return_to,
        candidate_verb_id=verb.id if source == "candidate" else None,
        admin_href="/admin#candidates" if source == "candidate" else None,
        ui_strings=ui_strings,
        ui_lang=ui_lang,
    )

    return HTMLResponse(html)
