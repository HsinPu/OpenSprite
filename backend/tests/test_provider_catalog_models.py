from uuid import uuid4

import pytest

from opensprite_backend.providers.catalog_models import canonical_base_url, provider_name, valid_provider_id


def test_provider_identity_preserves_builtins_and_accepts_canonical_uuid():
    assert all(valid_provider_id(item) for item in ("openai", "anthropic", "openrouter", str(uuid4())))
    assert not any(valid_provider_id(item) for item in (None, 1, "custom", "../key", "00000000-0000-0000-0000-000000000000"))


def test_endpoint_normalization_preserves_api_prefix():
    assert canonical_base_url("https://EXAMPLE.com/v1/") == "https://example.com/v1"
    assert canonical_base_url("http://localhost:11434/v1", allow_insecure_local=True) == "http://localhost:11434/v1"
    assert canonical_base_url("http://[::1]:8080/v1", allow_insecure_local=True) == "http://[::1]:8080/v1"


@pytest.mark.parametrize("url", ["http://example.com/v1", "https://user:key@example.com", "https://example.com?", "https://example.com#", "https://example.com/../v1", "https://169.254.169.254", "https://0.0.0.0", "file:///tmp", " https://example.com", "https://example.com:0"])
def test_reject_unsafe_endpoint(url):
    with pytest.raises(ValueError):
        canonical_base_url(url, allow_insecure_local=True)


def test_local_http_requires_explicit_acknowledgement():
    with pytest.raises(ValueError, match="insecure_base_url"):
        canonical_base_url("http://127.0.0.1:8080/v1")


def test_name_normalizes_unicode():
    assert provider_name(" Cafe\u0301 ") == "Caf\u00e9"
    with pytest.raises(ValueError):
        provider_name(" ")
