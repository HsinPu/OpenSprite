from opensprite.config.schema import Config
from opensprite.media.factory import media_router_status, reload_media_router
from opensprite.media.router import MediaRouter


def test_media_router_status_reports_provider_availability():
    router = MediaRouter(image_provider=object(), video_provider=object())

    assert media_router_status(router) == {
        "vision_enabled": True,
        "ocr_enabled": False,
        "speech_enabled": False,
        "video_enabled": True,
    }


def test_reload_media_router_reuses_existing_router_and_applies_config(tmp_path):
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.speech.enabled = True
    config.speech.api_key = "speech-secret"
    config.speech.model = "whisper-1"

    original_image_provider = object()
    current_router = MediaRouter(image_provider=original_image_provider)

    reloaded_router = reload_media_router(current_router, config)

    assert reloaded_router is current_router
    assert reloaded_router.image_provider is None
    assert reloaded_router.speech_provider is not None
    assert reloaded_router.speech_provider.default_model == "whisper-1"
    assert media_router_status(reloaded_router) == {
        "vision_enabled": False,
        "ocr_enabled": False,
        "speech_enabled": True,
        "video_enabled": False,
    }
