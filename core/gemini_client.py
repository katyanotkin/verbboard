"""Shared google-genai client (Vertex AI backend) for every Gemini call.

Replaces the deprecated ``vertexai.generative_models`` SDK. The client is built
lazily and cached per (project, location), so there is one per process in practice.
Calls are synchronous; async callers wrap them in ``asyncio.to_thread``.
"""

from __future__ import annotations

from functools import lru_cache

from google import genai
from google.genai import types

from core.settings import load_settings


@lru_cache(maxsize=None)
def _build_client(project: str, location: str) -> genai.Client:
    return genai.Client(vertexai=True, project=project, location=location)


def get_gemini_client(project: str | None = None, location: str | None = None) -> genai.Client:
    settings = load_settings()
    return _build_client(project or settings.google_cloud_project, location or settings.gcp_region)


def generate_gemini_text(
    model: str,
    prompt: str,
    *,
    json_output: bool = False,
    project: str | None = None,
) -> str:
    """Single-prompt generation at temperature 0; returns ``response.text`` ('' if empty)."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json" if json_output else None,
        temperature=0,
    )
    response = get_gemini_client(project).models.generate_content(model=model, contents=prompt, config=config)
    return response.text or ""
