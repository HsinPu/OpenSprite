# Contracts

These OpenAPI 3.1 documents are authoritative for frontend/backend HTTP and SSE behavior.
Requests and responses reject unknown fields; revisions, bounded pagination, same-origin protections and sanitized errors remain part of each boundary.

| Document | Boundary |
| --- | --- |
| provider-connections | Built-in Provider connections and text model discovery |
| custom-providers | UUID-based Chat Completions providers, model catalog and encrypted write-only credentials |
| ai-settings | Model selection, Context/output budgets, response mode, continuation, delivery and prompt logging |
| agent-chat | Durable conversations, idempotent text Runs, cancellation, history and SSE |
| execution-settings | Installed Loop/policy metadata and selection for future Runs; Host API v2 |
| execution-plugin-packages | Static wheel import, cache inventory/removal, provenance and Docker deployment bundles |
| workspaces | Managed scopes, active selection, mounts and non-destructive catalog removal |
| general-settings | Interface locale and time zone |
| conversation-settings | Startup, send behavior, scroll and execution panel |
| local-authentication | Trusted-local/password modes, bootstrap and process-memory sessions |
| local-paths | User-initiated native path selection |
| app-info | Product/build identity |

The clean core has no Tools, approvals, Skills, custom Agent/Subagent, MCP or schedule contracts.
Their retired endpoints return 404. Chat accepts no action definitions and publishes only core text/model/compaction/execution events.
Provider wire actions fail as invalid responses instead of becoming an execution path.

Execution plugin metadata can report incompatible installed versions, but only API v2 can be selected or newly imported.
Retired cached packages remain inspectable; their deployment is rejected. Import does not install or run Python code.
Provider payloads, credentials, internal prompts and hidden reasoning are excluded from public events.
Agent chat uses HTTP/SSE; no WebSocket, webhook, runtime installer or application CLI is provided.
