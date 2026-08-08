"""Text hashing and diff helpers shared by file-change tools."""

from __future__ import annotations

import difflib
import hashlib


DEFAULT_DIFF_MAX_CHARS = 12_000


def text_sha256(content: str) -> str:
    """Return a stable UTF-8 SHA256 hash for text content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def format_unified_diff(
    display_path: str,
    before: str | None,
    after: str | None,
    *,
    max_chars: int = DEFAULT_DIFF_MAX_CHARS,
) -> str:
    """Return a bounded unified diff for text before/after states."""
    if before == after:
        return "(no changes)"

    before_text = before or ""
    after_text = after or ""
    fromfile = "/dev/null" if before is None else f"a/{display_path}"
    tofile = "/dev/null" if after is None else f"b/{display_path}"
    diff = "\n".join(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )
    if not diff:
        if before is None:
            diff = f"--- /dev/null\n+++ b/{display_path}\n@@\n(empty file created)"
        elif after is None:
            diff = f"--- a/{display_path}\n+++ /dev/null\n@@\n(empty file deleted)"
        else:
            diff = "(no changes)"
    if len(diff) > max_chars:
        return diff[:max_chars] + f"\n... (diff truncated, total {len(diff)} chars)"
    return diff
