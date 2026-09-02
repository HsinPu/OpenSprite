"""Local stdio MCP Server configuration and lifecycle routes."""

from typing import cast

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from opensprite_backend.mcp import McpConnections
from opensprite_backend.models import (
    CreateMcpServerRequest,
    McpErrorCode,
    McpErrorDetail,
    McpErrorEnvelope,
    McpServerListResponse,
    McpServerSummary,
    McpToolListResponse,
    PutMcpServerRequest,
)


router = APIRouter()

MCP_ERROR_STATUS = {
    McpErrorCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
    McpErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    McpErrorCode.SERVER_DISABLED: status.HTTP_409_CONFLICT,
    McpErrorCode.SERVER_NOT_RUNNING: status.HTTP_409_CONFLICT,
    McpErrorCode.SERVER_START_FAILED: status.HTTP_502_BAD_GATEWAY,
    McpErrorCode.SERVER_STOP_FAILED: status.HTTP_502_BAD_GATEWAY,
    McpErrorCode.SERVER_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    McpErrorCode.SERVER_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    McpErrorCode.TOOLS_NOT_SUPPORTED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    McpErrorCode.TOOL_CATALOG_INVALID: status.HTTP_422_UNPROCESSABLE_ENTITY,
    McpErrorCode.REMOTE_URL_BLOCKED: status.HTTP_400_BAD_REQUEST,
    McpErrorCode.AUTHENTICATION_REQUIRED: status.HTTP_401_UNAUTHORIZED,
    McpErrorCode.TLS_VERIFICATION_FAILED: status.HTTP_502_BAD_GATEWAY,
    McpErrorCode.REDIRECT_NOT_ALLOWED: status.HTTP_502_BAD_GATEWAY,
    McpErrorCode.PROTOCOL_UNSUPPORTED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    McpErrorCode.MCP_STORE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    McpErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}
MCP_PUBLIC_ERRORS = {
    McpErrorCode.INVALID_REQUEST: ("Request validation failed.", False),
    McpErrorCode.NOT_FOUND: ("The MCP server was not found.", False),
    McpErrorCode.SERVER_DISABLED: ("The MCP server is disabled.", False),
    McpErrorCode.SERVER_NOT_RUNNING: ("The MCP server is not running.", False),
    McpErrorCode.SERVER_START_FAILED: ("The MCP server could not be started.", False),
    McpErrorCode.SERVER_STOP_FAILED: ("The MCP server could not be stopped.", True),
    McpErrorCode.SERVER_UNREACHABLE: ("The MCP server is unavailable.", True),
    McpErrorCode.SERVER_TIMEOUT: ("The MCP server did not respond before the timeout.", True),
    McpErrorCode.TOOLS_NOT_SUPPORTED: ("The MCP server does not provide tools.", False),
    McpErrorCode.TOOL_CATALOG_INVALID: ("The MCP tool catalog cannot be used safely.", False),
    McpErrorCode.REMOTE_URL_BLOCKED: ("The MCP network destination is not allowed.", False),
    McpErrorCode.AUTHENTICATION_REQUIRED: ("The MCP server requires authentication that is not supported yet.", False),
    McpErrorCode.TLS_VERIFICATION_FAILED: ("The MCP server TLS certificate could not be verified.", False),
    McpErrorCode.REDIRECT_NOT_ALLOWED: ("The MCP server attempted an HTTP redirect.", False),
    McpErrorCode.PROTOCOL_UNSUPPORTED: ("The MCP server protocol is not supported.", False),
    McpErrorCode.MCP_STORE_UNAVAILABLE: ("MCP server settings are unavailable.", True),
    McpErrorCode.INTERNAL_ERROR: ("An internal error occurred.", False),
}
MCP_ERROR_RESPONSES = {
    code: {"model": McpErrorEnvelope}
    for code in (400, 404, 409, 422, 500, 502, 503, 504)
}


def mcp_error_response(code: McpErrorCode, *, retryable: bool | None = None) -> JSONResponse:
    message, default_retryable = MCP_PUBLIC_ERRORS[code]
    envelope = McpErrorEnvelope(
        error=McpErrorDetail(
            code=code,
            message=message,
            retryable=default_retryable if retryable is None else retryable,
        )
    )
    return JSONResponse(
        status_code=MCP_ERROR_STATUS[code],
        content=envelope.model_dump(mode="json", by_alias=True),
    )


def _connections(request: Request) -> McpConnections:
    return cast(McpConnections, request.app.state.mcp_connections)


@router.get("/api/mcp/servers", operation_id="listMcpServers", response_model=McpServerListResponse, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def list_mcp_servers(connections: McpConnections = Depends(_connections)) -> McpServerListResponse:
    return await connections.list_servers()


@router.post("/api/mcp/servers", operation_id="createMcpServer", status_code=201, response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def create_mcp_server(payload: CreateMcpServerRequest, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    return await connections.create_server(payload)


@router.get("/api/mcp/servers/{server_id}", operation_id="getMcpServer", response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def get_mcp_server(server_id: str, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    listing = await connections.list_servers()
    for server in listing.servers:
        if server.id == server_id:
            return server
    from opensprite_backend.mcp.manager import McpConnectionError
    raise McpConnectionError(McpErrorCode.NOT_FOUND)


@router.put("/api/mcp/servers/{server_id}", operation_id="putMcpServer", response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def put_mcp_server(server_id: str, payload: PutMcpServerRequest, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    return await connections.update_server(server_id, payload)


@router.delete("/api/mcp/servers/{server_id}", operation_id="deleteMcpServer", status_code=204, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def delete_mcp_server(server_id: str, connections: McpConnections = Depends(_connections)) -> Response:
    await connections.delete_server(server_id)
    return Response(status_code=204)


@router.post("/api/mcp/servers/{server_id}/test", operation_id="testMcpServer", response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def test_mcp_server(server_id: str, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    return await connections.test_server(server_id)


@router.post("/api/mcp/servers/{server_id}/start", operation_id="startMcpServer", response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def start_mcp_server(server_id: str, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    return await connections.start_server(server_id)


@router.post("/api/mcp/servers/{server_id}/stop", operation_id="stopMcpServer", response_model=McpServerSummary, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def stop_mcp_server(server_id: str, connections: McpConnections = Depends(_connections)) -> McpServerSummary:
    return await connections.stop_server(server_id)


@router.get("/api/mcp/servers/{server_id}/tools", operation_id="listMcpTools", response_model=McpToolListResponse, responses=MCP_ERROR_RESPONSES, tags=["mcp"])
async def list_mcp_tools(server_id: str, connections: McpConnections = Depends(_connections)) -> McpToolListResponse:
    return await connections.list_tools(server_id)
