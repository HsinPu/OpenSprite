"""Media analysis providers and routers."""

from .audio import OpenAICompatibleSpeechProvider
from .artifacts import (
    MEDIA_ARTIFACT_KINDS,
    count_media_artifacts,
    is_media_artifact_kind,
    media_artifact_gap_follow_up_instruction,
)
from .audio_input import AudioInputPreprocessResult, AudioInputPreprocessor
from .base import ImageAnalysisProvider, SpeechToTextProvider, VideoAnalysisProvider
from .image import MiniMaxImageProvider, OpenAICompatibleImageProvider, create_image_analysis_provider
from .outbound import outbound_media_error_result
from .service import (
    AgentMediaService,
    INBOUND_AUDIO_EXTENSIONS,
    INBOUND_IMAGE_EXTENSIONS,
    INBOUND_MEDIA_UNSUPPORTED_PAYLOAD_REASON,
    INBOUND_VIDEO_EXTENSIONS,
    MEDIA_ONLY_HISTORY_MARKER,
)
from .video import OpenAICompatibleVideoProvider
from .router import (
    MediaRouter,
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
