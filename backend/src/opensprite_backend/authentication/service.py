"""Argon2id password verification and process-local session ownership."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from threading import RLock
from typing import Callable, Protocol
import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..app_paths import AppPaths
from ..models import AuthAuthenticated, AuthSetupRequired, AuthStatus, AuthTrustedLocal, AuthUnauthenticated
from .store import AccessMode, AccessRecord, AccessStoreError, JsonAccessStore, JsonBootstrapStore


_SESSION_IDLE = timedelta(hours=12)


class LocalAuthenticationError(Exception):
    def __init__(self, code: str, *, retry_after: int | None = None) -> None:
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AuthResult:
    status: AuthAuthenticated
    token: str


@dataclass(slots=True)
class _Session:
    created_at: datetime
    last_seen_at: datetime


class LocalAuthenticationOperations(Protocol):
    async def status(self, token: str | None) -> AuthStatus: ...
    async def setup(self, bootstrap_token: str, password: str) -> AuthResult: ...
    async def login(self, password: str) -> AuthResult: ...
    async def authenticate(self, token: str | None) -> AuthAuthenticated | None: ...
    async def logout(self, token: str | None) -> None: ...
    async def logout_all(self) -> None: ...
    async def change_password(self, token: str | None, current_password: str, new_password: str) -> AuthResult: ...


class UnavailableLocalAuthentication:
    async def status(self, token: str | None) -> AuthStatus:
        del token
        raise LocalAuthenticationError("access_store_unavailable")

    def __getattr__(self, name: str):
        del name
        async def unavailable(*args, **kwargs):
            del args, kwargs
            raise LocalAuthenticationError("access_store_unavailable")
        return unavailable


class LocalAuthentication:
    def __init__(
        self,
        access_store: JsonAccessStore,
        bootstrap_store: JsonBootstrapStore,
        *,
        clock: Callable[[], datetime] | None = None,
        password_hasher: PasswordHasher | None = None,
        access_mode: AccessMode = AccessMode.PASSWORD_REQUIRED,
    ) -> None:
        self._access = access_store
        self._bootstrap = bootstrap_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._hasher = password_hasher or PasswordHasher(
            time_cost=2,
            memory_cost=19 * 1024,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )
        self._sessions: dict[str, _Session] = {}
        self._failed_attempts = 0
        self._blocked_until: datetime | None = None
        self._lock = RLock()
        self._mutation_lock = asyncio.Lock()
        self._access_mode = access_mode

    async def status(self, token: str | None) -> AuthStatus:
        if self._access_mode is AccessMode.TRUSTED_LOCAL:
            return AuthTrustedLocal()
        try:
            if self._access.get() is None:
                return AuthSetupRequired()
        except AccessStoreError as error:
            raise LocalAuthenticationError("access_store_unavailable") from error
        authenticated = await self.authenticate(token)
        return authenticated if authenticated is not None else AuthUnauthenticated()

    async def authenticate(self, token: str | None) -> AuthAuthenticated | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
        now = self._now()
        with self._lock:
            session = self._sessions.get(digest)
            if session is None:
                return None
            if now - session.last_seen_at >= _SESSION_IDLE:
                self._sessions.pop(digest, None)
                return None
            session.last_seen_at = now
            return AuthAuthenticated(expiresAt=now + _SESSION_IDLE)

    async def setup(self, bootstrap_token: str, password: str) -> AuthResult:
        self._require_password_mode()
        normalized = _validated_password(password)
        async with self._mutation_lock:
            try:
                if self._access.get() is not None:
                    raise LocalAuthenticationError("setup_unavailable")
                bootstrap = self._bootstrap.get()
            except AccessStoreError as error:
                raise LocalAuthenticationError("access_store_unavailable") from error
            now = self._now()
            supplied = hashlib.sha256(bootstrap_token.encode("utf-8")).hexdigest()
            if bootstrap is None or now >= bootstrap.expires_at or not hmac.compare_digest(supplied, bootstrap.token_hash):
                raise LocalAuthenticationError("setup_unavailable")
            password_hash = await asyncio.to_thread(self._hasher.hash, normalized)
            try:
                self._access.set(AccessRecord(password_hash))
                self._bootstrap.delete()
            except AccessStoreError as error:
                raise LocalAuthenticationError("access_store_unavailable") from error
            self._failed_attempts = 0
            self._blocked_until = None
            return self._issue(now)

    async def login(self, password: str) -> AuthResult:
        self._require_password_mode()
        now = self._now()
        self._require_not_throttled(now)
        try:
            record = self._access.get()
        except AccessStoreError as error:
            raise LocalAuthenticationError("access_store_unavailable") from error
        if record is None:
            raise LocalAuthenticationError("setup_required")
        normalized = unicodedata.normalize("NFC", password)
        valid = False
        try:
            valid = await asyncio.to_thread(self._hasher.verify, record.password_hash, normalized)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False
        if not valid:
            self._record_failure(now)
            raise LocalAuthenticationError("invalid_credentials")
        with self._lock:
            self._failed_attempts = 0
            self._blocked_until = None
        if self._hasher.check_needs_rehash(record.password_hash):
            try:
                replacement = await asyncio.to_thread(self._hasher.hash, normalized)
                self._access.set(AccessRecord(replacement))
            except AccessStoreError as error:
                raise LocalAuthenticationError("access_store_unavailable") from error
        return self._issue(now)

    async def logout(self, token: str | None) -> None:
        if token:
            digest = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
            with self._lock:
                self._sessions.pop(digest, None)

    async def logout_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    async def change_password(self, token: str | None, current_password: str, new_password: str) -> AuthResult:
        self._require_password_mode()
        if await self.authenticate(token) is None:
            raise LocalAuthenticationError("authentication_required")
        normalized_new = _validated_password(new_password)
        async with self._mutation_lock:
            try:
                record = self._access.get()
            except AccessStoreError as error:
                raise LocalAuthenticationError("access_store_unavailable") from error
            if record is None:
                raise LocalAuthenticationError("setup_required")
            normalized_current = unicodedata.normalize("NFC", current_password)
            try:
                valid = await asyncio.to_thread(self._hasher.verify, record.password_hash, normalized_current)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                valid = False
            if not valid:
                raise LocalAuthenticationError("invalid_credentials")
            replacement = await asyncio.to_thread(self._hasher.hash, normalized_new)
            try:
                self._access.set(AccessRecord(replacement))
            except AccessStoreError as error:
                raise LocalAuthenticationError("access_store_unavailable") from error
            with self._lock:
                self._sessions.clear()
            return self._issue(self._now())

    def _issue(self, now: datetime) -> AuthResult:
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self._lock:
            self._sessions[digest] = _Session(now, now)
        return AuthResult(AuthAuthenticated(expiresAt=now + _SESSION_IDLE), token)

    def _require_not_throttled(self, now: datetime) -> None:
        with self._lock:
            if self._blocked_until is not None and now < self._blocked_until:
                seconds = max(1, int((self._blocked_until - now).total_seconds() + 0.999))
                raise LocalAuthenticationError("rate_limited", retry_after=seconds)

    def _record_failure(self, now: datetime) -> None:
        with self._lock:
            self._failed_attempts += 1
            if self._failed_attempts >= 5:
                delay = min(60, 2 ** (self._failed_attempts - 5))
                self._blocked_until = now + timedelta(seconds=delay)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise LocalAuthenticationError("access_store_unavailable")
        return value.astimezone(UTC)

    def _require_password_mode(self) -> None:
        if self._access_mode is AccessMode.TRUSTED_LOCAL:
            raise LocalAuthenticationError("authentication_not_enabled")


def _validated_password(password: str) -> str:
    normalized = unicodedata.normalize("NFC", password)
    if not 15 <= len(normalized) <= 128 or any(character in normalized for character in ("\x00", "\r", "\n")):
        raise LocalAuthenticationError("invalid_request")
    return normalized


def create_local_authentication(paths: AppPaths, *, access_mode: AccessMode = AccessMode.PASSWORD_REQUIRED) -> LocalAuthentication:
    return LocalAuthentication(JsonAccessStore(paths.access_file), JsonBootstrapStore(paths.access_bootstrap_file), access_mode=access_mode)
