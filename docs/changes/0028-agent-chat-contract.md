# 0028 - Agent chat contract

## Objective

Fix the smallest durable Conversation and Run boundary before implementing
database, Agent, Provider inference, streaming, or frontend behavior.

## Changes

- Added the authoritative strict OpenAPI 3.1 contract for conversations,
  messages, idempotent Run creation, Run snapshots, SSE events, and cancellation.
- Fixed Provider, response-mode, Run status, error, identifier, pagination, and
  safe event payload shapes.
- Documented the one-message/one-Run workflow, dependency direction, SQLite
  ownership, bounded Agent loop, governed Tool Registry, and restart behavior.
- Explicitly excluded keyword routing, the archived Task lifecycle, hidden
  reasoning, speculative tools, subagents, MCP, memory, and search.

## Public impact

The repository now defines a draft Agent chat API boundary. No runtime route,
database, model request, tool, or frontend behavior is implemented by this
documentation-only slice.

## Verification

- Static contract tests validate the exact operations and core strict schemas.
- JSON parsing verifies the contract document is valid JSON.
- Repository diff whitespace checks run before commit.

## Remaining work

Implement SQLite persistence, the bounded Agent loop, native Provider inference
adapters, the Run/SSE API, and the real frontend workflow as separate changes.
