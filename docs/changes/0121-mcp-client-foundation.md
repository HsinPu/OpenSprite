# MCP Client Foundation

## Objective

以官方 MCP Python SDK 建立 Windows stdio、協定協商與受控 Tool 呼叫的最小基礎，不連接或執行任何第三方 MCP Server。

## Changes

- 新增官方 MCP SDK v2 核心相依，不加入 `mcp[cli]` 或 OpenSprite CLI。
- 將 Backend Python 支援範圍明確限定為 3.12 與 3.13，避免 MCP v2 與既有 FastAPI pin 在 Python 3.14 的 Starlette 解析衝突。
- 新增 repository-owned stdio MCP fixture，僅提供 deterministic echo 與 process-id Tool。
- 驗證 client protocol negotiation、server identity、tools capability、`tools/list` 與 `tools/call`。

## Public impact

本切片只加入 runtime dependency 與測試 fixture；沒有 API、設定、子程序自動啟動、Agent Tool 或使用者資料格式變更。

## Verification

- MCP SDK foundation focused tests 通過。
- Backend dependency lock 與 installed dependency check 納入驗證。

## Remaining work

MCP Server 設定、生命週期、Tool discovery、人工確認、Agent execution、receipt 與 UI 尚未實作。
