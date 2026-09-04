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

CONTEXT_LIMIT_ERROR = PublicRunError(
    code="context_limit_exceeded",
    message="必要的近期對話超過目前選擇的內容上限。",
    retryable=False,
)

CONTEXT_PREPARATION_ERROR = PublicRunError(
    code="context_preparation_failed",
    message="暫時無法準備這次對話的模型內容。",
    retryable=True,
)

INVALID_PROVIDER_RESPONSE = _INFERENCE_ERRORS[
    InferenceFailure.INVALID_PROVIDER_RESPONSE
]

INTERNAL_ERROR = PublicRunError(
    code="internal_error",
    message="本機服務暫時無法完成這次執行。",
    retryable=True,
)

SCHEDULED_TOOL_APPROVAL_REQUIRED = PublicRunError(
    code="scheduled_tool_approval_required",
    message="排程執行需要人工核准的工具，因此已安全停止。",
    retryable=False,
)

WORKSPACE_CONTEXT_ERROR = PublicRunError(
    code="workspace_store_unavailable",
    message="工作區執行內容暫時無法安全載入。",
    retryable=True,
)


def inference_error(failure: InferenceFailure) -> PublicRunError:
    if failure is InferenceFailure.CONTEXT_LIMIT_EXCEEDED:
        return CONTEXT_LIMIT_ERROR
    return _INFERENCE_ERRORS[failure]
