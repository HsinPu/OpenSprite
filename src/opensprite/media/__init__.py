"""Media analysis providers and routers."""

from .audio import OpenAICompatibleSpeechProvider
from .base import ImageAnalysisProvider, SpeechToTextProvider, VideoAnalysisProvider
from .image import MiniMaxImageProvider, OpenAICompatibleImageProvider, create_image_analysis_provider
from .video import OpenAICompatibleVideoProvider
from .router import (
    AgentMediaService,
    AudioInputPreprocessResult,
    AudioInputPreprocessor,
    INBOUND_AUDIO_EXTENSIONS,
    INBOUND_IMAGE_EXTENSIONS,
    INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
    INBOUND_VIDEO_EXTENSIONS,
    MEDIA_ARTIFACT_KINDS,
    MEDIA_ONLY_HISTORY_MARKER,
    MediaRouter,
    count_media_artifacts,
    is_media_artifact_kind,
    media_artifact_gap_follow_up_instruction,
    outbound_media_error_result,
)

__all__ = [
    "ImageAnalysisProvider",
    "SpeechToTextProvider",
    "VideoAnalysisProvider",
    "MediaRouter",
    "MiniMaxImageProvider",
    "OpenAICompatibleImageProvider",
    "OpenAICompatibleSpeechProvider",
    "OpenAICompatibleVideoProvider",
    "create_image_analysis_provider",
    "AgentMediaService",
    "AudioInputPreprocessResult",
    "AudioInputPreprocessor",
    "INBOUND_AUDIO_EXTENSIONS",
    "INBOUND_IMAGE_EXTENSIONS",
    "INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON",
    "INBOUND_VIDEO_EXTENSIONS",
    "MEDIA_ARTIFACT_KINDS",
    "MEDIA_ONLY_HISTORY_MARKER",
    "count_media_artifacts",
    "is_media_artifact_kind",
    "media_artifact_gap_follow_up_instruction",
    "outbound_media_error_result",
]
