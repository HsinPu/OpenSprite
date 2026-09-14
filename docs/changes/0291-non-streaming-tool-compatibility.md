# Explicit non-streaming tool compatibility

- Custom providers expose `nonStreamingTools` on mutation and `non_streaming_tools` on reads/persistence; default false preserves native streaming.
- The immutable execution endpoint retains this choice for the run.
- When enabled, requests containing tool definitions use JSON Chat Completions; requests without tools retain SSE.
- Full responses are bounded to 4 MiB and validated before emitting events. Only formal message.tool_calls execute; text JSON remains text.
- No automatic retry, model switch, forced tool choice, or live provider configuration changes.
- UI response delivery remains distinct from provider transport; compatibility requests wait for a complete response.

Verification:
- Backend focused regression: 19 passed (non-streaming tools, custom provider routes and service). Pytest reported a cache-directory permission warning; assertions passed.
- Frontend focused regression: 11 passed across CustomProviderCreate and customProviders.
- Frontend typecheck and production build passed; existing large-chunk advisory remains.
- git diff --check passed.
- Tool round trips use mocked HTTP responses, not a live-provider end-to-end test. Browser visual review and live LiteLLM auto tool-choice verification remain pending.
- Installed runtime was not updated; no version bump, commit, or push performed.
