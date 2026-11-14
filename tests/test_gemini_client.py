import pathlib
import re
from unittest.mock import MagicMock

from core import gemini_client

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_no_runtime_module_imports_vertexai() -> None:
    pattern = re.compile(r"^\s*(import vertexai|from vertexai)", re.MULTILINE)
    offenders = [
        str(path.relative_to(_ROOT))
        for folder in ("app", "core", "tools")
        for path in (_ROOT / folder).rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_client_factory_is_lazy_and_cached(monkeypatch) -> None:
    fake_client_cls = MagicMock()
    monkeypatch.setattr(gemini_client.genai, "Client", fake_client_cls)
    gemini_client._build_client.cache_clear()
    try:
        fake_client_cls.assert_not_called()
        first = gemini_client.get_gemini_client("proj", "loc")
        second = gemini_client.get_gemini_client("proj", "loc")
        assert first is second
        fake_client_cls.assert_called_once_with(vertexai=True, project="proj", location="loc")
    finally:
        gemini_client._build_client.cache_clear()
