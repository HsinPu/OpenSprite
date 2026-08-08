from types import SimpleNamespace

from opensprite.integrations.llm import provider_discovery


def test_fetch_openai_compatible_models_probes_v1_fallback(monkeypatch):
    seen_urls = []

    def fake_read_json_url(url, *, headers=None):
        seen_urls.append((url, headers))
        if url == "https://example.test/v1/models":
            return {
                "data": [
                    {"id": "first-live"},
                    {"id": ""},
                    {"id": "first-live"},
                    {"id": "second-live"},
                ]
            }
        return {"data": []}

    monkeypatch.setattr(provider_discovery, "_read_json_url", fake_read_json_url)

    models = provider_discovery.fetch_openai_compatible_models(
        "secret",
        "https://example.test",
    )

    assert models == ["first-live", "second-live"]
    assert seen_urls == [
        (
            "https://example.test/models",
            {"Accept": "application/json", "Authorization": "Bearer secret"},
        ),
        (
            "https://example.test/v1/models",
            {"Accept": "application/json", "Authorization": "Bearer secret"},
        ),
    ]


def test_fetch_openai_compatible_models_accepts_models_endpoint(monkeypatch):
    seen_urls = []

    def fake_read_json_url(url, *, headers=None):
        seen_urls.append((url, headers))
        if url == "https://example.test/v1/models":
            return {"data": [{"id": "fallback-live"}]}
        return {"data": []}

    monkeypatch.setattr(provider_discovery, "_read_json_url", fake_read_json_url)

    models = provider_discovery.fetch_openai_compatible_models(
        "",
        "https://example.test/models",
    )

    assert models == ["fallback-live"]
    assert seen_urls == [
        ("https://example.test/models", {"Accept": "application/json"}),
        ("https://example.test/v1/models", {"Accept": "application/json"}),
    ]


def test_fetch_codex_models_filters_and_sorts(monkeypatch):
    def fake_read_json_url(url, *, headers=None):
        return {
            "models": [
                {"slug": "hidden", "visibility": "hide", "priority": 1},
                {"slug": "unsupported", "supported_in_api": False, "priority": 2},
                {"slug": "later", "priority": 20},
                {"slug": "earlier", "priority": 10},
                {"slug": "earlier", "priority": 10},
            ]
        }

    monkeypatch.setattr(provider_discovery, "_read_json_url", fake_read_json_url)
    monkeypatch.setattr(
        "opensprite.integrations.auth.codex.load_or_refresh_codex_token",
        lambda app_home=None: SimpleNamespace(access_token="codex-token"),
    )

    assert provider_discovery.fetch_codex_models(object()) == ["earlier", "later"]


def test_fetch_openrouter_image_models_filters_by_modality(monkeypatch):
    def fake_read_json_url(url, *, headers=None):
        return {
            "data": [
                {
                    "id": "text-only",
                    "architecture": {"input_modalities": ["text"]},
                },
                {
                    "id": "vision-one",
                    "architecture": {"input_modalities": ["text", "image"]},
                },
                {
                    "id": "vision-one",
                    "architecture": {"input_modalities": ["image"]},
                },
                {"id": "missing-modalities", "architecture": {}},
                {
                    "id": "vision-two",
                    "architecture": {"input_modalities": ["IMAGE", "text"]},
                },
            ]
        }

    monkeypatch.setattr(provider_discovery, "_read_json_url", fake_read_json_url)

    assert provider_discovery.fetch_openrouter_image_models() == [
        "vision-one",
        "vision-two",
    ]
