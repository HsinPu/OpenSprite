"""Explicit local MCP configuration, process lifecycle, and discovery owner."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from ..app_paths import AppPaths
from ..credentials import (
    CredentialStore,
    CredentialStoreError,
    EncryptedJsonCredentialStore,
)
from ..models import (
    CreateMcpServerRequest,
    McpBearerAuthenticationInput,
    McpBearerAuthenticationSummary,
    McpErrorCode,
    McpNoAuthentication,
    McpServerListResponse,
    McpServerStatus,
    McpServerSummary,
    McpStdioTransport,
    McpStreamableHttpTransport,
    McpToolAnnotations as PublicMcpToolAnnotations,
    McpToolListResponse,
    McpToolSummary,
    PutMcpServerRequest,
)
from .config import (
    JsonMcpConfigStore,
    McpBearerAuthenticationConfig,
    McpConfigStore,
    McpConfigStoreError,
    McpServerConfig,
    McpNoAuthenticationConfig,
    McpStdioConfig,
    McpStreamableHttpConfig,
    mcp_bearer_credential_id,
)
from .session import (
    DiscoveredMcpTool,
    McpClientSession,
    McpSessionError,
    McpSessionFactory,
    OfficialMcpSessionFactory,
)
from .network import McpNetworkPolicyError, normalize_streamable_http_url
from .tool_adapter import McpToolAdapter
from ..tools.definition import Tool


class McpConnectionError(Exception):
    def __init__(self, code: McpErrorCode, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code.value)


class McpConnections(Protocol):
    async def startup(self) -> None: ...

    async def close(self) -> None: ...

    async def list_servers(self) -> McpServerListResponse: ...

    async def create_server(self, payload: CreateMcpServerRequest) -> McpServerSummary: ...

    async def update_server(self, server_id: str, payload: PutMcpServerRequest) -> McpServerSummary: ...

    async def delete_server(self, server_id: str) -> None: ...

    async def test_server(self, server_id: str) -> McpServerSummary: ...

    async def start_server(self, server_id: str) -> McpServerSummary: ...

    async def stop_server(self, server_id: str) -> McpServerSummary: ...

    async def list_tools(self, server_id: str) -> McpToolListResponse: ...

    async def snapshot_tools(self) -> tuple[Tool, ...]: ...


class UnavailableMcpConnections:
    async def startup(self) -> None:
        raise McpConfigStoreError

    async def close(self) -> None:
        return None

    def __getattr__(self, name: str):
        del name

        async def unavailable(*args, **kwargs):
            del args, kwargs
            raise McpConfigStoreError

        return unavailable


@dataclass(slots=True)
class _ServerRuntime:
    status: McpServerStatus
    session: McpClientSession | None = None
    tools: tuple[DiscoveredMcpTool, ...] = ()
    error_code: str | None = None
    invocation_lock: asyncio.Lock | None = None


class McpConnectionManager:
    def __init__(
        self,
        store: McpConfigStore,
        session_factory: McpSessionFactory | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._store = store
        self._credentials = credential_store
        self._session_factory = session_factory or OfficialMcpSessionFactory(
            credential_store=credential_store
        )
        self._lock = asyncio.Lock()
        self._runtime: dict[str, _ServerRuntime] = {}
        self._operation_locks: dict[str, asyncio.Lock] = {}
        self._closed = False

    async def startup(self) -> None:
        async with self._lock:
            self._closed = False
            configs = self._store.get()
            for config in configs:
                self._runtime.setdefault(
                    config.id,
                    _ServerRuntime(
                        McpServerStatus.STOPPED if config.enabled else McpServerStatus.DISABLED
                    ),
                )
        for config in configs:
            if config.enabled and config.start_on_launch:
                try:
                    await self._start(config.id, persist_enabled=False)
                except McpConnectionError:
                    continue

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            sessions = [runtime.session for runtime in self._runtime.values() if runtime.session is not None]
            for runtime in self._runtime.values():
                runtime.session = None
                runtime.tools = ()
                runtime.status = McpServerStatus.STOPPED
        for session in sessions:
            try:
                await session.close()
            except McpSessionError:
                continue

    async def list_servers(self) -> McpServerListResponse:
        async with self._lock:
            return McpServerListResponse(
                servers=[self._summary(config) for config in self._store.get()]
            )

    async def create_server(
        self,
        payload: CreateMcpServerRequest,
    ) -> McpServerSummary:
        config = _config_from_request(str(uuid4()), payload, enabled=False)
        desired_token = _requested_bearer_token(payload)
        async with self._lock:
            self._require_open()
            configs = self._store.get()
            if len(configs) >= 32:
                raise McpConnectionError(McpErrorCode.INVALID_REQUEST)
            self._commit_config_and_credential(
                before_config=None,
                before_token=None,
                after_config=config,
                after_token=desired_token,
                configs=(*configs, config),
            )
            self._runtime[config.id] = _ServerRuntime(McpServerStatus.DISABLED)
            self._operation_locks[config.id] = asyncio.Lock()
            return self._summary(config)

    async def update_server(
        self,
        server_id: str,
        payload: PutMcpServerRequest,
    ) -> McpServerSummary:
        async with self._operation_lock(server_id):
            await self._stop_locked(server_id, persist_enabled=False)
            async with self._lock:
                configs = self._store.get()
                current = _find_config(configs, server_id)
                replacement = _config_from_request(current.id, payload, enabled=False)
                before_token = self._stored_bearer_token(current)
                desired_token = _requested_bearer_token(payload)
                if (
                    isinstance(replacement.authentication, McpBearerAuthenticationConfig)
                    and desired_token is None
                ):
                    if not isinstance(current.authentication, McpBearerAuthenticationConfig):
                        raise McpConnectionError(McpErrorCode.INVALID_REQUEST)
                    if before_token is None:
                        raise McpConnectionError(
                            McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                            retryable=True,
                        )
                    desired_token = before_token
                self._commit_config_and_credential(
                    before_config=current,
                    before_token=before_token,
                    after_config=replacement,
                    after_token=desired_token,
                    configs=tuple(replacement if item.id == server_id else item for item in configs),
                )
                self._runtime[server_id] = _ServerRuntime(McpServerStatus.DISABLED)
                return self._summary(replacement)

    async def delete_server(self, server_id: str) -> None:
        async with self._operation_lock(server_id):
            await self._stop_locked(server_id, persist_enabled=False)
            async with self._lock:
                configs = self._store.get()
                current = _find_config(configs, server_id)
                before_token = self._stored_bearer_token(current)
                self._commit_config_and_credential(
                    before_config=current,
                    before_token=before_token,
                    after_config=None,
                    after_token=None,
                    configs=tuple(item for item in configs if item.id != server_id),
                )
                self._runtime.pop(server_id, None)

    async def test_server(self, server_id: str) -> McpServerSummary:
        async with self._lock:
            config = _find_config(self._store.get(), server_id)
            config = _validated_stored_config(config)
        try:
            session = await self._session_factory.open(config)
            tools = await session.discover_tools()
        except McpSessionError as error:
            raise _public_session_error(error) from error
        try:
            runtime = _ServerRuntime(
                status=McpServerStatus.CONNECTED,
                session=session,
                tools=tools,
            )
            return self._summary(config, runtime)
        finally:
            try:
                await session.close()
            except McpSessionError:
                pass

    async def start_server(self, server_id: str) -> McpServerSummary:
        return await self._start(server_id, persist_enabled=True)

    async def stop_server(self, server_id: str) -> McpServerSummary:
        return await self._stop(server_id, persist_enabled=True)

    async def list_tools(self, server_id: str) -> McpToolListResponse:
        async with self._lock:
            config = _find_config(self._store.get(), server_id)
            runtime = self._runtime.get(server_id)
            if runtime is None or runtime.status is not McpServerStatus.CONNECTED:
                raise McpConnectionError(McpErrorCode.SERVER_NOT_RUNNING)
            del config
            return McpToolListResponse(tools=[_public_tool(tool) for tool in runtime.tools])

    async def snapshot_tools(self) -> tuple[Tool, ...]:
        async with self._lock:
            adapters: list[Tool] = []
            for runtime in self._runtime.values():
                if runtime.status is not McpServerStatus.CONNECTED or runtime.session is None:
                    continue
                invocation_lock = runtime.invocation_lock or asyncio.Lock()
                runtime.invocation_lock = invocation_lock
                adapters.extend(
                    McpToolAdapter(tool, runtime.session, invocation_lock)
                    for tool in runtime.tools
                    if tool.definition is not None
                )
            return tuple(adapters)

    async def _start(self, server_id: str, *, persist_enabled: bool) -> McpServerSummary:
        async with self._operation_lock(server_id):
            return await self._start_locked(server_id, persist_enabled=persist_enabled)

    async def _start_locked(self, server_id: str, *, persist_enabled: bool) -> McpServerSummary:
        async with self._lock:
            self._require_open()
            configs = self._store.get()
            config = _find_config(configs, server_id)
            config = _validated_stored_config(config)
            runtime = self._runtime.setdefault(server_id, _ServerRuntime(McpServerStatus.STOPPED))
            if runtime.status is McpServerStatus.CONNECTED:
                return self._summary(config, runtime)
            runtime.status = McpServerStatus.STARTING
            runtime.error_code = None
            if persist_enabled and not config.enabled:
                config = config.with_enabled(True)
                self._store.set(tuple(config if item.id == server_id else item for item in configs))
        try:
            session = await self._session_factory.open(config)
            tools = await session.discover_tools()
        except McpSessionError as error:
            async with self._lock:
                self._runtime[server_id] = _ServerRuntime(
                    McpServerStatus.ERROR,
                    error_code=error.code,
                )
            raise _public_session_error(error) from error
        async with self._lock:
            if self._closed:
                await session.close()
                raise McpConnectionError(McpErrorCode.SERVER_STOP_FAILED)
            self._runtime[server_id] = _ServerRuntime(
                McpServerStatus.CONNECTED,
                session=session,
                tools=tools,
                invocation_lock=asyncio.Lock(),
            )
            return self._summary(config, self._runtime[server_id])

    async def _stop(self, server_id: str, *, persist_enabled: bool) -> McpServerSummary:
        async with self._operation_lock(server_id):
            return await self._stop_locked(server_id, persist_enabled=persist_enabled)

    async def _stop_locked(self, server_id: str, *, persist_enabled: bool) -> McpServerSummary:
        async with self._lock:
            configs = self._store.get()
            config = _find_config(configs, server_id)
            runtime = self._runtime.setdefault(server_id, _ServerRuntime(McpServerStatus.DISABLED))
            session = runtime.session
            runtime.session = None
            runtime.tools = ()
            runtime.status = McpServerStatus.STOPPING if session is not None else McpServerStatus.DISABLED
            if persist_enabled and config.enabled:
                config = config.with_enabled(False)
                self._store.set(tuple(config if item.id == server_id else item for item in configs))
        if session is not None:
            try:
                await session.close()
            except McpSessionError as error:
                async with self._lock:
                    self._runtime[server_id] = _ServerRuntime(McpServerStatus.ERROR, error_code=error.code)
                raise _public_session_error(error) from error
        async with self._lock:
            self._runtime[server_id] = _ServerRuntime(
                McpServerStatus.DISABLED if not config.enabled else McpServerStatus.STOPPED
            )
            return self._summary(config, self._runtime[server_id])

    def _operation_lock(self, server_id: str) -> asyncio.Lock:
        return self._operation_locks.setdefault(server_id, asyncio.Lock())

    def _summary(
        self,
        config: McpServerConfig,
        runtime: _ServerRuntime | None = None,
    ) -> McpServerSummary:
        state = runtime or self._runtime.get(config.id) or _ServerRuntime(
            McpServerStatus.STOPPED if config.enabled else McpServerStatus.DISABLED
        )
        supported = sum(tool.definition is not None for tool in state.tools)
        return McpServerSummary(
            id=config.id,
            name=config.name,
            enabled=config.enabled,
            startOnLaunch=config.start_on_launch,
            transport=_public_transport(config),
            status=state.status,
            protocolVersion=state.session.protocol_version if state.session else None,
            errorCode=state.error_code,
            toolCount=supported,
            unsupportedToolCount=len(state.tools) - supported,
            authentication=self._public_authentication(config),
        )

    def _public_authentication(
        self,
        config: McpServerConfig,
    ) -> McpNoAuthentication | McpBearerAuthenticationSummary:
        if isinstance(config.authentication, McpNoAuthenticationConfig):
            return McpNoAuthentication()
        store = self._require_credential_store()
        try:
            configured = store.fingerprint(mcp_bearer_credential_id(config.id)) is not None
        except CredentialStoreError as error:
            raise McpConnectionError(
                McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                retryable=True,
            ) from error
        return McpBearerAuthenticationSummary(configured=configured)

    def _stored_bearer_token(self, config: McpServerConfig) -> str | None:
        if isinstance(config.authentication, McpNoAuthenticationConfig):
            return None
        store = self._require_credential_store()
        try:
            return store.get(mcp_bearer_credential_id(config.id))
        except CredentialStoreError as error:
            raise McpConnectionError(
                McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                retryable=True,
            ) from error

    def _require_credential_store(self) -> CredentialStore:
        if self._credentials is None:
            raise McpConnectionError(
                McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                retryable=True,
            )
        return self._credentials

    def _commit_config_and_credential(
        self,
        *,
        before_config: McpServerConfig | None,
        before_token: str | None,
        after_config: McpServerConfig | None,
        after_token: str | None,
        configs: tuple[McpServerConfig, ...],
    ) -> None:
        credential_involved = any(
            config is not None
            and isinstance(config.authentication, McpBearerAuthenticationConfig)
            for config in (before_config, after_config)
        )
        if not credential_involved:
            self._store.set(configs)
            return
        if after_config is not None:
            server_id = after_config.id
        elif before_config is not None:
            server_id = before_config.id
        else:
            raise McpConnectionError(McpErrorCode.INVALID_REQUEST)
        store = self._require_credential_store()
        credential_id = mcp_bearer_credential_id(server_id)

        def restore() -> None:
            if before_token is None:
                store.delete(credential_id)
            else:
                store.set(credential_id, before_token)

        try:
            if after_token is None:
                store.delete(credential_id)
            else:
                store.set(credential_id, after_token)
        except CredentialStoreError as error:
            try:
                restore()
            except CredentialStoreError:
                pass
            raise McpConnectionError(
                McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                retryable=True,
            ) from error
        try:
            self._store.set(configs)
        except Exception:
            try:
                restore()
            except CredentialStoreError as error:
                raise McpConnectionError(
                    McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
                    retryable=True,
                ) from error
            raise

    def _require_open(self) -> None:
        if self._closed:
            raise McpConnectionError(McpErrorCode.SERVER_START_FAILED)


def _config_from_request(
    server_id: str,
    payload: CreateMcpServerRequest | PutMcpServerRequest,
    *,
    enabled: bool,
) -> McpServerConfig:
    if isinstance(payload.transport, McpStdioTransport):
        executable = _resolved_executable(payload.transport.executable)
        working_directory = _resolved_directory(payload.transport.workingDirectory)
        transport = McpStdioConfig(
            executable=str(executable),
            arguments=tuple(payload.transport.arguments),
            working_directory=None if working_directory is None else str(working_directory),
        )
    else:
        try:
            url = normalize_streamable_http_url(payload.transport.url)
        except McpNetworkPolicyError as error:
            raise McpConnectionError(McpErrorCode.REMOTE_URL_BLOCKED) from error
        transport = McpStreamableHttpConfig(url=url)
    authentication = (
        McpNoAuthenticationConfig()
        if isinstance(payload.authentication, McpNoAuthentication)
        else McpBearerAuthenticationConfig()
    )
    return McpServerConfig(
        id=server_id,
        name=payload.name.strip(),
        transport=transport,
        authentication=authentication,
        enabled=enabled,
        start_on_launch=payload.startOnLaunch,
    )


def _requested_bearer_token(
    payload: CreateMcpServerRequest | PutMcpServerRequest,
) -> str | None:
    authentication = payload.authentication
    if not isinstance(authentication, McpBearerAuthenticationInput):
        return None
    return (
        None
        if authentication.token is None
        else authentication.token.get_secret_value()
    )


def _resolved_executable(value: str) -> Path:
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise McpConnectionError(McpErrorCode.INVALID_REQUEST) from error
    if not path.is_absolute() or not resolved.is_file() or path.is_symlink():
        raise McpConnectionError(McpErrorCode.INVALID_REQUEST)
    return resolved


def _resolved_directory(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise McpConnectionError(McpErrorCode.INVALID_REQUEST) from error
    if not path.is_absolute() or not resolved.is_dir() or path.is_symlink():
        raise McpConnectionError(McpErrorCode.INVALID_REQUEST)
    return resolved


def _validated_stored_config(config: McpServerConfig) -> McpServerConfig:
    if isinstance(config.transport, McpStreamableHttpConfig):
        try:
            return replace(config, transport=replace(config.transport, url=normalize_streamable_http_url(config.transport.url)))
        except McpNetworkPolicyError as error:
            raise McpConnectionError(McpErrorCode.REMOTE_URL_BLOCKED) from error
    transport = config.transport
    return replace(
        config,
        transport=replace(
            transport,
            executable=str(_resolved_executable(transport.executable)),
            working_directory=(
            None
            if transport.working_directory is None
            else str(_resolved_directory(transport.working_directory))
            ),
        ),
    )


def _public_transport(config: McpServerConfig) -> McpStdioTransport | McpStreamableHttpTransport:
    transport = config.transport
    if isinstance(transport, McpStdioConfig):
        return McpStdioTransport(
            executable=transport.executable,
            arguments=list(transport.arguments),
            workingDirectory=transport.working_directory,
        )
    return McpStreamableHttpTransport(url=transport.url)


def _find_config(
    configs: tuple[McpServerConfig, ...],
    server_id: str,
) -> McpServerConfig:
    for config in configs:
        if config.id == server_id:
            return config
    raise McpConnectionError(McpErrorCode.NOT_FOUND)


def _public_session_error(error: McpSessionError) -> McpConnectionError:
    mapping = {
        "server_start_failed": McpErrorCode.SERVER_START_FAILED,
        "server_stop_failed": McpErrorCode.SERVER_STOP_FAILED,
        "server_unreachable": McpErrorCode.SERVER_UNREACHABLE,
        "server_timeout": McpErrorCode.SERVER_TIMEOUT,
        "tools_not_supported": McpErrorCode.TOOLS_NOT_SUPPORTED,
        "tool_catalog_invalid": McpErrorCode.TOOL_CATALOG_INVALID,
        "remote_url_blocked": McpErrorCode.REMOTE_URL_BLOCKED,
        "authentication_required": McpErrorCode.AUTHENTICATION_REQUIRED,
        "tls_verification_failed": McpErrorCode.TLS_VERIFICATION_FAILED,
        "redirect_not_allowed": McpErrorCode.REDIRECT_NOT_ALLOWED,
        "protocol_unsupported": McpErrorCode.PROTOCOL_UNSUPPORTED,
        "credential_store_unavailable": McpErrorCode.CREDENTIAL_STORE_UNAVAILABLE,
    }
    return McpConnectionError(mapping.get(error.code, McpErrorCode.SERVER_UNREACHABLE), retryable=error.code in {"server_unreachable", "server_timeout"})


def _public_tool(tool: DiscoveredMcpTool) -> McpToolSummary:
    return McpToolSummary(
        id=tool.id,
        serverId=tool.server_id,
        originalName=tool.original_name,
        title=tool.title,
        description=tool.description,
        supported=tool.definition is not None,
        unsupportedReason=tool.unsupported_reason,
        annotations=PublicMcpToolAnnotations(
            readOnlyHint=tool.annotations.read_only,
            destructiveHint=tool.annotations.destructive,
            idempotentHint=tool.annotations.idempotent,
            openWorldHint=tool.annotations.open_world,
        ),
    )


def create_mcp_connection_manager(
    app_paths: AppPaths,
    credential_store: CredentialStore | None = None,
) -> McpConnectionManager:
    store = credential_store or EncryptedJsonCredentialStore(
        app_paths.credential_file,
        app_paths.credential_key_file,
    )
    return McpConnectionManager(
        JsonMcpConfigStore(app_paths.mcp_settings_file),
        credential_store=store,
    )
