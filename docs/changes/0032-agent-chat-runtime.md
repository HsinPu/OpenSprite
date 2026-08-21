# 0032 - Agent chat runtime

## Objective

Compose settings, Provider connections, Conversation storage, the bounded Agent,
native inference, Run task ownership, HTTP, SSE replay, and cancellation into
one local desktop runtime.

## Changes

- Added an Agent chat application service that requires a selected, currently
  connected Provider before atomically accepting a Message and Run.
- Added strict HTTP models and six routes for conversation pages, visible
  messages, idempotent Run creation, Run snapshots, semantic SSE, and bodyless
  cancellation.
- Added exact SSE serialization with durable sequence ids, semantic event names,
  safe JSON payloads, `Last-Event-ID` replay, no-cache headers, and terminal
  closure.
- Added fixed chat error codes/statuses/messages and mapped persistence,
  settings, connection, conflict, not-found, and cancellation failures without
  exposing private exceptions.
- Composed one SQLite repository, empty read-only Tool Registry, Agent loop, Run
  manager, native gateway, and Agent chat service per system lifespan.
- Added startup interruption before HTTP binding and shutdown unbinding before
  task interruption and Provider client closure.
- Kept import, factory construction, empty reads, empty runtime startup, and
  shutdown side-effect free when no database exists.

## Public impact

The draft routes in `contracts/agent-chat.openapi.json` are now live in the local
backend. State-changing routes remain protected by exact same-origin policy.
Conversation data is created only after the first accepted message. Existing
Provider and AI-settings routes and payloads are unchanged.

## Verification

- Application tests cover real settings/connection gating, idempotent start,
  background completion, persisted lists/messages, SSE replay, and startup
  interruption.
- HTTP tests cover exact camel-case payloads, 202 start/cancel responses,
  bodyless cancellation, safe error envelopes, `Last-Event-ID`, exact SSE frames,
  strict generated request schema, and same-origin mutation enforcement.
- Runtime tests use the real composition to mark a persisted orphaned Run
  interrupted before serving it.
- Existing Provider, settings, local-security, AppPaths, runtime lifecycle, and
  contract tests run together with the new chat tests.
- The complete backend suite, Python compilation, dependency checks, CodeGraph,
  and whitespace checks run before commit.

## Remaining work

Replace the frontend's fake conversation list, fake messages, fake assistant
response, and fake execution panel with the live HTTP/SSE workflow.
