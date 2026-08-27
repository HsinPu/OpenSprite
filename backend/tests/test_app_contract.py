"""Provider-conformance checks against the candidate FastAPI foundation."""

from datetime import UTC, datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from opensprite_backend import create_app
from opensprite_backend.models import (
    ErrorCode,
    OpenRouterModel,
    OpenRouterModelListResponse,
    ProviderId,
    ProviderListResponse,
    ProviderStatus,
    ProviderSummary,
)
from opensprite_backend.provider_connections import ProviderConnectionError

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "provider-connections.openapi.json"
)
AI_SETTINGS_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "ai-settings.openapi.json"
)


def summary(provider_id: ProviderId, connected: bool) -> ProviderSummary:
    name = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "openrouter": "OpenRouter",
    }[provider_id]
    return ProviderSummary(
        id=provider_id,
        name=name,
        connected=connected,
        status=(
            ProviderStatus.CONNECTED
            if connected
            else ProviderStatus.DISCONNECTED
        ),
        credentialPreview="••••1234" if connected else None,
        lastCheckedAt=datetime(2026, 8, 20, 8, 30, tzinfo=UTC)
        if connected
        else None,
    )


class RecordingProviderConnections:
    def __init__(self) -> None:
        self.connected_key: str | None = None
        self.disconnected_provider: ProviderId | None = None

    async def list_providers(self) -> ProviderListResponse:
        return ProviderListResponse(
            providers=[
                summary("openai", False),
                summary("anthropic", False),
                summary("openrouter", False),
            ]
        )

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        return OpenRouterModelListResponse(
            models=[OpenRouterModel(id="openai/gpt-4", name="GPT-4")]
        )

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        self.connected_key = api_key
        return summary(provider_id, True)

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        return summary(provider_id, True)

    async def disconnect(self, provider_id: ProviderId) -> None:
        self.disconnected_provider = provider_id


class FailingProviderConnections(RecordingProviderConnections):
    def __init__(self, code: ErrorCode, private_text: str) -> None:
        super().__init__()
        self.code = code
        self.private_text = private_text

    def failure(self) -> ProviderConnectionError:
        error = ProviderConnectionError(self.code)
        error.args = (self.private_text,)
        return error

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        del provider_id, api_key
        raise self.failure()

    async def test(self, provider_id: ProviderId) -> ProviderSummary:
        del provider_id
        raise self.failure()

    async def list_openrouter_models(self) -> OpenRouterModelListResponse:
        raise self.failure()


class ExplodingProviderConnections(RecordingProviderConnections):
    def __init__(self, private_text: str) -> None:
        super().__init__()
        self.private_text = private_text

    async def connect(
        self,
        provider_id: ProviderId,
        api_key: str,
    ) -> ProviderSummary:
        del provider_id, api_key
        raise RuntimeError(self.private_text)


def test_app_routes_and_operation_ids_match_contract() -> None:
    schema = create_app().openapi()
    operations = {
        (path, method, operation["operationId"])
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "put", "post", "delete"}
    }

    assert operations == {
        ("/healthz", "get", "getHealth"),
        ("/api/settings/ai", "get", "getAiSettings"),
        ("/api/settings/ai", "put", "putAiSettings"),
        ("/api/settings/general", "get", "getGeneralSettings"),
        ("/api/settings/general", "put", "putGeneralSettings"),
        ("/api/conversations", "get", "listConversations"),
        (
            "/api/conversations/{conversation_id}/messages",
            "get",
            "listConversationMessages",
        ),
        ("/api/runs", "post", "startRun"),
        ("/api/runs/{run_id}", "get", "getRun"),
        ("/api/runs/{run_id}/events", "get", "streamRunEvents"),
        ("/api/runs/{run_id}/cancel", "post", "cancelRun"),
        ("/api/providers", "get", "listProviders"),
        (
            "/api/providers/openrouter/models",
            "post",
            "listOpenRouterModels",
        ),
        (
            "/api/providers/{provider_id}/connection",
            "put",
            "putProviderConnection",
        ),
        (
            "/api/providers/{provider_id}/connection",
            "delete",
            "deleteProviderConnection",
        ),
        (
            "/api/providers/{provider_id}/connection/test",
            "post",
            "testProviderConnection",
        ),
    }


@pytest.mark.parametrize("path", ["/openapi.json", "/docs", "/redoc"])
def test_runtime_contract_and_documentation_routes_are_disabled(path: str) -> None:
    response = TestClient(create_app()).get(path)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "providers",
    [
        [
            summary("openai", False),
            summary("openai", False),
            summary("openrouter", False),
        ],
        [
            summary("anthropic", False),
            summary("openai", False),
            summary("openrouter", False),
        ],
        [
            ProviderSummary(
                id="openai",
                name="Anthropic",
                connected=False,
                status=ProviderStatus.DISCONNECTED,
                credentialPreview=None,
                lastCheckedAt=None,
            ),
            summary("anthropic", False),
            summary("openrouter", False),
        ],
    ],
    ids=["duplicate", "reversed", "mismatched-name"],
)
def test_provider_catalog_rejects_noncanonical_entries(
    providers: list[ProviderSummary],
) -> None:
    with pytest.raises(ValidationError):
        ProviderListResponse(providers=providers)


def test_generated_public_models_align_with_authoritative_contract() -> None:
    generated = create_app().openapi()["components"]["schemas"]
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))[
        "components"
    ]["schemas"]

    for schema_name in (
        "ProviderSummary",
        "ProviderListResponse",
        "PutProviderConnectionRequest",
        "ErrorDetail",
        "ErrorEnvelope",
    ):
        assert generated[schema_name]["required"] == contract[schema_name][
            "required"
        ]

    generated_key = generated["PutProviderConnectionRequest"]["properties"][
        "apiKey"
    ]
    contract_key = contract["PutProviderConnectionRequest"]["properties"][
        "apiKey"
    ]
    assert generated_key["minLength"] == contract_key["minLength"]
    assert generated_key["maxLength"] == contract_key["maxLength"]


def test_generated_error_schemas_keep_provider_and_ai_settings_codes_separate() -> None:
    generated = create_app().openapi()
    schemas = generated["components"]["schemas"]
    model_contract = json.loads(
        AI_SETTINGS_CONTRACT_PATH.read_text(encoding="utf-8")
    )["components"]["schemas"]

    assert "settings_store_unavailable" not in schemas["ErrorCode"]["enum"]
    assert schemas["AiSettingsErrorCode"]["enum"] == model_contract[
        "ErrorCode"
    ]["enum"]
    assert schemas["AiSettingsErrorDetail"]["required"] == model_contract[
        "ErrorDetail"
    ]["required"]
    assert schemas["AiSettingsErrorEnvelope"]["required"] == model_contract[
        "ErrorEnvelope"
    ]["required"]

    provider_schema = generated["paths"]["/api/providers"]["get"][
        "responses"
    ]["503"]["content"]["application/json"]["schema"]["$ref"]
    settings_schema = generated["paths"]["/api/settings/ai"]["get"][
        "responses"
    ]["503"]["content"]["application/json"]["schema"]["$ref"]
    assert provider_schema.endswith("/ErrorEnvelope")
    assert settings_schema.endswith("/AiSettingsErrorEnvelope")


def test_health_is_liveness_only() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_default_provider_dependency_fails_closed() -> None:
    response = TestClient(create_app()).get("/api/providers")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "credential_store_unavailable",
            "message": "Secure credential storage is unavailable.",
            "retryable": True,
        }
    }


@pytest.mark.parametrize(
    ("code", "expected_status", "expected_message", "retryable", "operation"),
    [
        (
            ErrorCode.NOT_CONNECTED,
            409,
            "The provider is not connected.",
            False,
            "test",
        ),
        (
            ErrorCode.INVALID_CREDENTIALS,
            422,
            "The provider rejected the credential.",
            False,
            "put",
        ),
        (
            ErrorCode.PROVIDER_RATE_LIMITED,
            429,
            "The provider rate limit was reached.",
            True,
            "put",
        ),
        (
            ErrorCode.PROVIDER_UNREACHABLE,
            502,
            "The provider is temporarily unreachable.",
            True,
            "put",
        ),
        (
            ErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
            503,
            "Secure credential storage is unavailable.",
            True,
            "put",
        ),
        (
            ErrorCode.PROVIDER_TIMEOUT,
            504,
            "The provider did not respond before the timeout.",
            True,
            "put",
        ),
    ],
)
def test_documented_provider_errors_have_exact_safe_envelopes(
    code: ErrorCode,
    expected_status: int,
    expected_message: str,
    retryable: bool,
    operation: str,
) -> None:
    private_text = "private-provider-response-and-secret"
    provider_connections = FailingProviderConnections(code, private_text)
    client = TestClient(create_app(provider_connections))

    if operation == "test":
        response = client.post("/api/providers/openai/connection/test")
    else:
        response = client.put(
            "/api/providers/openai/connection",
            json={"apiKey": private_text},
        )

    assert response.status_code == expected_status
    assert response.json() == {
        "error": {
            "code": code.value,
            "message": expected_message,
            "retryable": retryable,
        }
    }
    assert private_text not in response.text


def test_unexpected_error_has_exact_safe_500_envelope() -> None:
    private_text = "private-unexpected-exception-and-secret"
    client = TestClient(
        create_app(ExplodingProviderConnections(private_text)),
        raise_server_exceptions=False,
    )

    response = client.put(
        "/api/providers/anthropic/connection",
        json={"apiKey": private_text},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred.",
            "retryable": False,
        }
    }
    assert private_text not in response.text


def test_success_examples_do_not_echo_the_secret() -> None:
    provider_connections = RecordingProviderConnections()
    client = TestClient(create_app(provider_connections))
    secret = "sk-test-never-return"

    response = client.put(
        "/api/providers/openai/connection",
        json={"apiKey": secret},
    )

    assert response.status_code == 200
    assert provider_connections.connected_key == secret
    assert secret not in response.text
    assert response.json()["id"] == "openai"
    assert response.json()["connected"] is True


def test_validation_error_is_fixed_and_does_not_echo_the_secret() -> None:
    client = TestClient(create_app(RecordingProviderConnections()))
    rejected_value = " " * 8

    response = client.put(
        "/api/providers/openai/connection",
        json={"apiKey": rejected_value},
    )

    assert response.status_code == 400
    assert rejected_value not in response.text
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Request validation failed.",
            "retryable": False,
        }
    }


def test_unknown_provider_has_stable_404_error() -> None:
    response = TestClient(create_app(RecordingProviderConnections())).delete(
        "/api/providers/unknown/connection"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unsupported_provider"


def test_connection_test_rejects_any_non_empty_body() -> None:
    response = TestClient(create_app(RecordingProviderConnections())).post(
        "/api/providers/anthropic/connection/test",
        content=b"{}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_openrouter_model_discovery_has_fixed_body_and_error_contract() -> None:
    response = TestClient(create_app(RecordingProviderConnections())).post(
        "/api/providers/openrouter/models",
        content=b"{}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"

    private_text = "private-model-list-error"
    error_response = TestClient(
        create_app(
            FailingProviderConnections(
                ErrorCode.PROVIDER_TIMEOUT,
                private_text,
            )
        )
    ).post("/api/providers/openrouter/models")

    assert error_response.status_code == 504
    assert error_response.json() == {
        "error": {
            "code": "provider_timeout",
            "message": "The provider did not respond before the timeout.",
            "retryable": True,
        }
    }
    assert private_text not in error_response.text


def test_openrouter_model_discovery_returns_fixed_model_shape() -> None:
    response = TestClient(create_app(RecordingProviderConnections())).post(
        "/api/providers/openrouter/models"
    )

    assert response.status_code == 200
    assert response.json() == {"models": [{"id": "openai/gpt-4", "name": "GPT-4"}]}


def test_delete_is_no_content() -> None:
    provider_connections = RecordingProviderConnections()
    response = TestClient(create_app(provider_connections)).delete(
        "/api/providers/anthropic/connection"
    )

    assert response.status_code == 204
    assert response.content == b""
    assert provider_connections.disconnected_provider == "anthropic"
