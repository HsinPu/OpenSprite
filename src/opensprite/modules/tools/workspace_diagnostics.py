"""Content-only post-edit diagnostics for workspace tool adapters."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

try:
    import yaml as _yaml  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    _yaml = None


def _run_post_edit_diagnostics(
    changed_files: list[tuple[Path, str, str]],
) -> tuple[list[str], list[str]]:
    """Return `(passes, failures)` for lightweight syntax/parse checks after edits."""
    passes: list[str] = []
    failures: list[str] = []
    for file_path, display_path, content in changed_files:
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            try:
                compile(content, display_path, "exec")
                passes.append(f"{display_path} [python_syntax]")
            except SyntaxError as exc:
                failures.append(
                    f"{display_path} [python_syntax]: {exc.msg} at line {exc.lineno or 0}:{exc.offset or 0}"
                )
            continue
        if suffix == ".json":
            try:
                json.loads(content)
                passes.append(f"{display_path} [json_parse]")
            except Exception as exc:
                failures.append(f"{display_path} [json_parse]: {exc}")
            continue
        if suffix == ".toml":
            try:
                tomllib.loads(content)
                passes.append(f"{display_path} [toml_parse]")
            except Exception as exc:
                failures.append(f"{display_path} [toml_parse]: {exc}")
            continue
        if suffix in {".yaml", ".yml"} and _yaml is not None:
            try:
                _yaml.safe_load(content)
                passes.append(f"{display_path} [yaml_parse]")
            except Exception as exc:
                failures.append(f"{display_path} [yaml_parse]: {exc}")
    return passes, failures


def format_post_edit_diagnostics(
    changed_files: list[tuple[Path, str, str]],
) -> tuple[str, bool]:
    """Render concise post-edit diagnostics for parser-checked file types."""
    passes, failures = _run_post_edit_diagnostics(changed_files)
    if failures:
        return (
            "\n\n".join(
                [
                    f"Post-edit diagnostics failed for {len(failures)} file(s).",
                    "\n".join(f"- {item}" for item in failures[:12]),
                ]
            ),
            True,
        )
    if passes:
        return (
            "Diagnostics:\n" + "\n".join(f"- {item} OK" for item in passes[:12]),
            False,
        )
    return "", False
