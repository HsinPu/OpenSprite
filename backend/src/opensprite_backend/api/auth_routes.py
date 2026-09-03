"""Single-owner local authentication routes."""

from typing import cast

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from ..authentication import LocalAuthenticationOperations
from ..authentication.middleware import SESSION_COOKIE
from ..models import (
    AuthErrorCode,
    AuthErrorDetail,
    AuthErrorEnvelope,
    AuthLoginRequest,
    AuthPasswordChangeRequest,
    AuthSetupRequest,
    AuthStatus,
)


router = APIRouter(tags=["authentication"])

_ERRORS = {
    "invalid_request": (400, "Request validation failed.", False),
    "invalid_credentials": (401, "Authentication failed.", False),
    "authentication_required": (401, "Authentication required.", False),
    "setup_required": (409, "Local access setup is required.", False),
    "setup_unavailable": (409, "Local access setup is unavailable.", False),
    "rate_limited": (429, "Too many authentication attempts.", True),
    "access_store_unavailable": (503, "Local access storage is unavailable.", True),
    "authentication_not_enabled": (409, "Password authentication is not enabled.", False),
    "internal_error": (500, "An internal error occurred.", False),
}


def auth_error_response(code: str, *, retry_after: int | None = None) -> JSONResponse:
    status_code, message, retryable = _ERRORS.get(code, _ERRORS["internal_error"])
    envelope = AuthErrorEnvelope(error=AuthErrorDetail(
        code=AuthErrorCode(code if code in _ERRORS else "internal_error"),
        message=message,
        retryable=retryable,
    ))
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"), headers=headers)


def _auth(request: Request) -> LocalAuthenticationOperations:
    return cast(LocalAuthenticationOperations, request.app.state.local_authentication)


def _token(request: Request) -> str | None:
    return cast(str | None, request.scope.get("state", {}).get("opensprite_session_token") or request.cookies.get(SESSION_COOKIE))


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, secure=True, httponly=True, samesite="strict", path="/")


def _clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="strict", path="/")


@router.get("/api/auth/status", operation_id="getAuthStatus", response_model=AuthStatus)
async def get_auth_status(request: Request, auth: LocalAuthenticationOperations = Depends(_auth)) -> AuthStatus:
    return await auth.status(request.cookies.get(SESSION_COOKIE))


@router.post("/api/auth/setup", operation_id="setupLocalAccess", response_model=AuthStatus)
async def setup_local_access(payload: AuthSetupRequest, response: Response, auth: LocalAuthenticationOperations = Depends(_auth)) -> AuthStatus:
    result = await auth.setup(payload.bootstrapToken.get_secret_value(), payload.password.get_secret_value())
    _set_session(response, result.token)
    return result.status


@router.post("/api/auth/login", operation_id="loginLocalAccess", response_model=AuthStatus)
async def login_local_access(payload: AuthLoginRequest, response: Response, auth: LocalAuthenticationOperations = Depends(_auth)) -> AuthStatus:
    result = await auth.login(payload.password.get_secret_value())
    _set_session(response, result.token)
    return result.status


@router.post("/api/auth/logout", operation_id="logoutLocalAccess", status_code=status.HTTP_204_NO_CONTENT)
async def logout_local_access(request: Request, response: Response, auth: LocalAuthenticationOperations = Depends(_auth)) -> Response:
    await auth.logout(_token(request))
    _clear_session(response)
    response.status_code = 204
    return response


@router.post("/api/auth/logout-all", operation_id="logoutAllLocalAccess", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_local_access(response: Response, auth: LocalAuthenticationOperations = Depends(_auth)) -> Response:
    await auth.logout_all()
    _clear_session(response)
    response.status_code = 204
    return response


@router.put("/api/auth/password", operation_id="changeLocalPassword", response_model=AuthStatus)
async def change_local_password(payload: AuthPasswordChangeRequest, request: Request, response: Response, auth: LocalAuthenticationOperations = Depends(_auth)) -> AuthStatus:
    result = await auth.change_password(_token(request), payload.currentPassword.get_secret_value(), payload.newPassword.get_secret_value())
    _set_session(response, result.token)
    return result.status
