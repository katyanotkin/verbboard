"""Guard against false-green string-path patches (issue #58).

`monkeypatch.setattr("core.x.name", fake)` / `patch("core.x.name")` replaces the
name only in module `core.x`. If `core.x` is where the object is DEFINED and
other app/core modules did `from core.x import name`, those modules keep the
real object, and the patch silently stops applying (negative assertions like
`assert_not_called()` then pass for the wrong reason). Such sites must go
through `tests.conftest.patch_everywhere`, which patches every holder.

This test walks the test sources with `ast`, resolves each string-path patch
and fails when its target is a defining module whose object is also bound in
other loaded app.*/core.* modules.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

from tests.conftest import modules_holding_same_object

TESTS_DIR = Path(__file__).parent

# Targets that are deliberately patched at their defining module.
# "module.attr" -> justification.
ALLOWLIST: dict[str, str] = {
    # get_db: the autouse `_no_real_firestore` fixture in conftest seeds
    # core.storage.firestore_db._db with a per-test FakeFirestore, so every
    # module's get_db() resolves to the fake regardless of import style.
    # Migrating these sites is step 3 of issue #58.
    "core.storage.firestore_db.get_db": "covered by autouse _no_real_firestore guard",
}

_PATCH_FUNCTION_NAMES = {"setattr", "patch"}


def _string_patch_sites(path: Path):
    """Yield (line, dotted target) for string-path patches in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _PATCH_FUNCTION_NAMES:
            is_patch_call = func.attr == "patch" or (
                func.attr == "setattr" and isinstance(func.value, ast.Name) and func.value.id == "monkeypatch"
            )
        elif isinstance(func, ast.Name) and func.id == "patch":
            is_patch_call = True
        else:
            is_patch_call = False
        first_arg = node.args[0]
        if is_patch_call and isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            target = first_arg.value
            if target.startswith(("app.", "core.")):
                yield node.lineno, target


def _defining_module_target(target: str):
    """Return dotted 'module.attr' if target names a module-level attribute whose
    object is defined in that very module, else None."""
    module_path, _, attribute_name = target.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None  # e.g. "pkg.module.Class.method": not a module-level name
    original = getattr(module, attribute_name, None)
    if original is None or getattr(original, "__module__", None) != module_path:
        return None
    return target


def _import_all_app_and_core_modules() -> None:
    """Load every app.*/core.* module so the holder scan does not depend on
    which other test files ran first."""
    for package_name in ("app", "core"):
        package = importlib.import_module(package_name)
        for module_info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
            importlib.import_module(module_info.name)


def _violations() -> list[str]:
    _import_all_app_and_core_modules()
    problems: list[str] = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path == Path(__file__):
            continue
        for line, target in _string_patch_sites(path):
            if target in ALLOWLIST or _defining_module_target(target) is None:
                continue
            holders = modules_holding_same_object(target)
            if holders:
                held = ", ".join(f"{module}.{name}" for module, name in sorted(holders))
                problems.append(
                    f"{path.relative_to(TESTS_DIR.parent)}:{line}: patches {target!r} at its defining "
                    f"module, but these modules hold their own copy: {held}. "
                    f"Use tests.conftest.patch_everywhere(monkeypatch, {target!r}, ...)."
                )
    return problems


def test_no_string_patch_targets_a_defining_module_with_other_holders() -> None:
    problems = _violations()
    assert not problems, "\n" + "\n".join(problems)
