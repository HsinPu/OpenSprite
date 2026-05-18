"""Video analysis tool for OpenSprite."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..media import MediaRouter
from .base import Tool
from .evidence import ToolEvidence, indexed_resource_id
from .saved_media import resolve_media_items
from .validation import NON_EMPTY_STRING_PATTERN


SUPPORTED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-matroska",
}


def _resolve_videos(
    *,
    current_videos: list[str] | None,
    workspace_resolver: Callable[[], Path] | None,
    video_path: str = "",
) -> tuple[list[str], str | None]:
    """Resolve videos from either current turn attachments or a saved workspace path."""
    return resolve_media_items(
        current_items=current_videos,
        workspace_resolver=workspace_resolver,
        media_path=video_path,
        media_label="video",
        supported_mime_types=SUPPORTED_VIDEO_MIME_TYPES,
    )


class AnalyzeVideoTool(Tool):
    """Tool to analyze video clips attached to the current user turn."""

    def __init__(
        self,
        media_router: MediaRouter,
        *,
        get_current_videos: Callable[[], list[str] | None],
        workspace_resolver: Callable[[], Path] | None = None,
    ):
        self._media_router = media_router
        self._get_current_videos = get_current_videos
        self._workspace_resolver = workspace_resolver

    @property
    def name(self) -> str:
        return "analyze_video"

    @property
    def description(self) -> str:
        return (
            "Analyze one video clip from the current user turn or a saved video in the session workspace. "
            "Use this when the user attached a video, or refers to an earlier saved video, and the task requires understanding what happens in it."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Required. What to analyze in the video and what kind of answer is needed.",
                    "pattern": NON_EMPTY_STRING_PATTERN,
                },
                "video_index": {
                    "type": "integer",
                    "description": "Optional. Zero-based index into the current turn's attached video clips. Defaults to 0.",
                    "default": 0,
                    "minimum": 0,
                },
                "video_path": {
                    "type": "string",
                    "description": "Optional. Relative path to a saved video in the current session workspace, such as videos/inbound-....mp4. Use this to inspect a video saved in an earlier turn.",
                },
            },
            "required": ["instruction"],
        }

    async def _execute(self, instruction: str, video_index: int = 0, video_path: str = "", **kwargs: Any) -> str:
        videos, error = _resolve_videos(
            current_videos=self._get_current_videos(),
            workspace_resolver=self._workspace_resolver,
            video_path=video_path,
        )
        if error:
            return error
        effective_index = 0 if video_path.strip() else video_index
        return await self._media_router.analyze_video(
            instruction=instruction,
            videos=videos,
            video_index=effective_index,
        )

    def build_evidence(self, params: Any, result: str, *, ok: bool) -> ToolEvidence:
        args = params if isinstance(params, dict) else {}
        video_path = str(args.get("video_path") or "").strip().replace("\\", "/")
        resource_id = f"video:{video_path}" if video_path else indexed_resource_id("video_index", args.get("video_index"))
        return ToolEvidence(
            name=self.name,
            args=dict(args or {}),
            ok=ok,
            resource_ids=(resource_id,),
            result_preview=str(result or "")[:240],
        )
