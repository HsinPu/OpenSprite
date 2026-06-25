import opensprite.media.factory as media_factory
from opensprite.config.schema import Config
from opensprite.media.factory import create_media_router, media_router_status, reload_media_router
from opensprite.media.router import MediaRouter


def test_media_router_status_reports_provider_availability():
    router = MediaRouter(image_provider=object(), video_provider=object())

    assert media_router_status(router) == {
        "vision_enabled": True,
        "ocr_enabled": False,
        "speech_enabled": False,
        "video_enabled": True,
    }


def test_create_media_router_uses_image_factory_for_vision_and_ocr(monkeypatch, tmp_path):
    calls = []

    def fake_create_image_analysis_provider(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(media_factory, "create_image_analysis_provider", fake_create_image_analysis_provider)
    config_path = tmp_path / "opensprite.json"
    Config.copy_template(config_path)
    config = Config.from_json(config_path)
    config.vision.enabled = True
    config.vision.provider = "openrouter"
    config.vision.api_key = "vision-key"
    config.vision.model = "vision-model"
    config.vision.base_url = "https://vision.example.test"
    config.ocr.enabled = True
    config.ocr.provider = "minimax"
    config.ocr.api_key = "ocr-key"
    config.ocr.model = "ocr-model"
    config.ocr.base_url = "https://ocr.example.test"

    router = create_media_router(config)

    assert router.image_provider is not None
    assert router.ocr_provider is not None
    assert calls == [
        {
            "provider": "openrouter",
            "api_key": "vision-key",
            "default_model": "vision-model",
            "base_url": "https://vision.example.test",
        },
        {
            "provider": "minimax",
            "api_key": "ocr-key",
            "default_model": "ocr-model",
            "base_url": "https://ocr.example.test",
        },
    ]


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
