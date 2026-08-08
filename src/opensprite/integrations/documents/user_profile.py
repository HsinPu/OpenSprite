"""Filesystem persistence and bootstrap handling for per-session user profiles."""

from __future__ import annotations

from pathlib import Path

from ..workspace.paths import get_bootstrap_dir, get_user_profile_file, get_user_profile_state_file
from ...modules.documents.safety import validate_durable_memory_text as _validate_durable_memory_text
from .managed_markdown import ManagedMarkdownDocument as _ManagedMarkdownDocument
from .progress_state import JsonProgressStore as _JsonProgressStore


RESPONSE_LANGUAGE_HEADER = "## Response language"
RL_START_MARKER = "<!-- OPENSPRITE:RESPONSE_LANGUAGE:START -->"
RL_END_MARKER = "<!-- OPENSPRITE:RESPONSE_LANGUAGE:END -->"
DEFAULT_RESPONSE_LANGUAGE_CONTENT = "- not set"
RESPONSE_LANGUAGE_INTRO = "This section is maintained by OpenSprite."

AUTO_PROFILE_HEADER = "## Auto-managed User Context"
START_MARKER = "<!-- OPENSPRITE:USER_PROFILE:START -->"
END_MARKER = "<!-- OPENSPRITE:USER_PROFILE:END -->"
DEFAULT_MANAGED_CONTENT = """### Communication Preferences
- No learned communication preferences yet.

### Work Context
- No learned work context yet.

### Stable Constraints
- No learned stable constraints yet."""
AUTO_PROFILE_INTRO = "This section is maintained by OpenSprite."


class UserProfileStore:
    """Persist one session's USER.md profile and its consolidation state."""

    def __init__(
        self,
        user_profile_file: Path,
        state_file: Path,
        *,
        bootstrap_text: str = "# User Profile\n\n",
    ):
        self.user_profile_file = Path(user_profile_file).expanduser()
        self.state = _JsonProgressStore(state_file)
        self.response_document = _ManagedMarkdownDocument(
            self.user_profile_file,
            start_marker=RL_START_MARKER,
            end_marker=RL_END_MARKER,
            default_content=DEFAULT_RESPONSE_LANGUAGE_CONTENT,
            heading=RESPONSE_LANGUAGE_HEADER,
            intro=RESPONSE_LANGUAGE_INTRO,
            anchor_heading=AUTO_PROFILE_HEADER,
            bootstrap_text=bootstrap_text,
        )
        self.profile_document = _ManagedMarkdownDocument(
            self.user_profile_file,
            start_marker=START_MARKER,
            end_marker=END_MARKER,
            default_content=DEFAULT_MANAGED_CONTENT,
            heading=AUTO_PROFILE_HEADER,
            intro=AUTO_PROFILE_INTRO,
            anchor_heading=None,
            bootstrap_text=bootstrap_text,
        )

    def read_text(self) -> str:
        # Ensure both managed regions exist (order: response language before profile).
        self.response_document.read_text()
        self.profile_document.read_text()
        return self.user_profile_file.read_text(encoding="utf-8")

    def read_response_language_block(self) -> str:
        return self.response_document.read_managed_block()

    def write_response_language_block(self, content: str) -> None:
        _validate_durable_memory_text(content)
        self.response_document.write_managed_block(content)

    def read_managed_block(self) -> str:
        return self.profile_document.read_managed_block()

    def write_managed_block(self, content: str) -> None:
        _validate_durable_memory_text(content)
        self.profile_document.write_managed_block(content)

    def load_state(self) -> dict[str, int]:
        return self.state.load_state()

    def save_state(self, state: dict[str, int]) -> None:
        self.state.save_state(state)

    def get_processed_index(self, session_id: str) -> int:
        return self.state.get_processed_index(session_id)

    def set_processed_index(self, session_id: str, index: int) -> None:
        self.state.set_processed_index(session_id, index)


def _reset_between_markers(
    text: str,
    start_marker: str,
    end_marker: str,
    inner: str,
) -> str:
    """Replace the inner content between markers, or return text unchanged if markers are missing."""
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1 or end <= start:
        return text
    start += len(start_marker)
    return text[:start] + "\n" + inner + "\n" + text[end:]


def _reset_managed_block(content: str) -> str:
    """Reset auto-managed blocks so new profiles do not inherit another user's data."""
    text = content or ""
    text = _reset_between_markers(
        text,
        RL_START_MARKER,
        RL_END_MARKER,
        DEFAULT_RESPONSE_LANGUAGE_CONTENT,
    )
    text = _reset_between_markers(text, START_MARKER, END_MARKER, DEFAULT_MANAGED_CONTENT)
    return text


def load_user_profile_bootstrap_text(
    app_home: str | Path | None = None,
    *,
    bootstrap_dir: str | Path | None = None,
) -> str:
    """Load the bootstrap USER.md template used to seed a new per-session profile file."""
    template_root = (
        Path(bootstrap_dir).expanduser() if bootstrap_dir is not None else get_bootstrap_dir(app_home)
    )
    template_file = template_root / "USER.md"
    if not template_file.exists():
        return "# User Profile\n\n"
    return _reset_managed_block(template_file.read_text(encoding="utf-8"))


def create_user_profile_store(
    app_home: str | Path | None,
    session_id: str | None,
    *,
    bootstrap_dir: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> UserProfileStore:
    """Create the per-session USER.md store for the given user/session scope."""
    return UserProfileStore(
        user_profile_file=get_user_profile_file(
            app_home,
            session_id=session_id,
            workspace_root=workspace_root,
        ),
        state_file=get_user_profile_state_file(
            app_home,
            session_id=session_id,
            workspace_root=workspace_root,
        ),
        bootstrap_text=load_user_profile_bootstrap_text(
            app_home,
            bootstrap_dir=bootstrap_dir,
        ),
    )
