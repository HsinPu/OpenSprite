"""Safe public Agent error mapping shared by loop termination paths."""

from __future__ import annotations

from opensprite_backend.conversations.models import PublicRunError
from opensprite_backend.inference.models import InferenceFailure


_INFERENCE_ERRORS = {
    InferenceFailure.PROVIDER_NOT_CONNECTED: PublicRunError(
        code="provider_not_connected",
        message="選擇的模型廠家目前尚未連線。",
        retryable=False,
    ),
    InferenceFailure.INVALID_CREDENTIALS: PublicRunError(
        code="invalid_credentials",
        message="模型廠家的 API 金鑰無效或已失效。",
        retryable=False,
    ),
    InferenceFailure.PROVIDER_RATE_LIMITED: PublicRunError(
        code="provider_rate_limited",
        message="模型廠家目前限制請求，請稍後再試。",
        retryable=True,
    ),
    InferenceFailure.PROVIDER_TIMEOUT: PublicRunError(
        code="provider_timeout",
        message="模型廠家回應逾時，請稍後再試。",
        retryable=True,
    ),
    InferenceFailure.PROVIDER_UNREACHABLE: PublicRunError(
        code="provider_unreachable",
        message="暫時無法連線到模型廠家，請稍後再試。",
        retryable=True,
    ),
    InferenceFailure.CREDENTIAL_STORE_UNAVAILABLE: PublicRunError(
        code="credential_store_unavailable",
        message="安全憑證儲存服務暫時無法使用。",
        retryable=True,
    ),
    InferenceFailure.INVALID_PROVIDER_RESPONSE: PublicRunError(
        code="invalid_provider_response",
        message="模型廠家回傳的資料無法安全使用。",
        retryable=False,
    ),
}

AGENT_LIMIT_ERROR = PublicRunError(
    code="agent_limit_reached",
    message="本次執行已達安全步驟上限。",
    retryable=False,
)

INVALID_PROVIDER_RESPONSE = _INFERENCE_ERRORS[
    InferenceFailure.INVALID_PROVIDER_RESPONSE
]

INTERNAL_ERROR = PublicRunError(
    code="internal_error",
    message="本機服務暫時無法完成這次執行。",
    retryable=True,
)


def inference_error(failure: InferenceFailure) -> PublicRunError:
    return _INFERENCE_ERRORS[failure]
