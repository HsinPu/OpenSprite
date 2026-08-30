# 0084 — Context compaction progress

## Objective

Tell the user when OpenSprite is actively summarizing older conversation
history without adding a synthetic message to the conversation.

## Changes

- Added the empty-payload semantic Run event
  `context.compaction.started` to the backend model, OpenAPI contract, strict
  frontend parser and SQLite event constraint.
- Upgraded the conversation database to schema v3 with an atomic v2 event-table
  replacement. The existing v1 migration chains through v2 to v3.
- Appended the event immediately before each real compaction model request,
  including the one permitted Provider context-limit retry.
- Displayed `正在整理較早的對話內容…` in the existing live assistant placeholder
  until a model or terminal event arrives.
- Added a deduplicated `整理較早的對話內容` step to current and historical
  execution records, with matching English and Japanese translations.
- Kept summaries, prompts, token counts and raw Message content out of the event
  payload and user-visible logs.

## Public impact

The bundled agent-chat SSE contract gains one additive event type. HTTP routes,
Run snapshots, Message payloads and error envelopes are unchanged. Existing v1
and v2 local databases upgrade in place without deleting Conversations,
Messages, Runs, compactions or events.

## Verification

- Targeted migration, contract, AgentLoop and frontend interaction tests passed
  after each implementation slice.
- Full backend pytest passed: 432 tests with 2 documented skips.
- Full frontend Vitest passed: 17 test files and 150 tests.
- Backend compileall, offline lock validation and dependency check passed.
- TypeScript typecheck and Vite production build passed. Vite retained its
  existing bundle-size warning.
- A SQLite online backup of the real schema-v2 database upgraded to v3 with all
  table counts preserved and `integrity_check=ok`; the temporary copy was then
  deleted.
- The real Windows install completed, migrated the live database to schema v3,
  returned HTTP 200 from `/healthz`, and loaded the existing Conversation and
  execution record without browser console errors.
- The isolated Windows installer test completed its application build twice but
  failed during final Temp `node_modules` cleanup because Windows PowerShell
  repeatedly reported an already-missing nested file. Both isolated Temp roots
  were subsequently removed safely; this does not affect the installed runtime.

## Remaining work

- Harden the pre-existing Windows installer test cleanup helper in a separate
  maintenance slice; product installation and this feature are verified.
