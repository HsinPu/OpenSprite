# Workspace Unicode migration compatibility

## Objective

Close review finding `OS-WS-R2-001` without weakening control-character or
bidirectional-text protections for new Workspace data.

## Changes

- Kept v1 catalog decoding compatible with the historical name contract, then
  sanitized newly disallowed names during the v1-to-v2 migration.
- Allowed Unicode ZWNJ (`U+200C`) and ZWJ (`U+200D`) in current Workspace names,
  managed directory names and mount aliases.
- Continued to reject control characters, surrogates and every other Unicode
  formatting character, including bidirectional overrides and isolates.
- Added real-filesystem tests for composed emoji and language joiners plus v1
  migration tests for preserved and sanitized names.

## Verification

- The five focused cases first reproduced the blocker, then passed after the
  fix; the complete Workspace suite passed `44` tests.
- Backend pytest passed `712` tests with `2` skipped; frontend Vitest passed
  `279` tests.
- Python compileall, uv lock, dependency checks, TypeScript typecheck,
  production build and Windows installer isolation passed.

## Remaining work

- No push or installed-computer update is included.
