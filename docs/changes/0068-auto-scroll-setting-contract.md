# 0068 Auto-scroll setting contract

## Objective

Persist one strict boolean preference that can control future chat-output
following without mixing conversation behavior into General Settings.

## Changes

- Added required boolean `autoScroll` to the Conversation Settings HTTP model,
  OpenAPI contract, frontend strict parser and state controller.
- Changed `.opensprite/config/conversation.json` to strict schema-v2 with the
  exact fields `startupView`, `sendBehavior` and `autoScroll`.
- Set the lazy, side-effect-free default to `new`, `enter` and `true`.
- Rejected schema-v1, missing, extra, duplicate and non-boolean values; no
  migration, compatibility fallback, feature flag or browser storage was added.
- Kept General Settings, AI Settings, Agent Chat and database contracts
  unchanged. The preference is not used by the chat UI until the next slice.

## Verification

- Focused backend store, API and OpenAPI tests passed.
- Focused frontend strict-client, controller consumers and TypeScript checks
  passed.
- Full backend verification passed: 388 tests with two platform-specific skips,
  compileall, offline lock and dependency checks.
- Full frontend verification passed: 14 test files and 123 tests, TypeScript
  typecheck and the Vite production build.
