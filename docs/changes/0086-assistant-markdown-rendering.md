# 0086 — Assistant Markdown rendering

## Objective

Render AI responses as readable Markdown in the browser while keeping the
stored and transported Message content as the original Markdown string.

## Changes

- Added a focused `MarkdownMessage` component using `react-markdown` and
  `remark-gfm` for persisted and streaming assistant responses.
- Kept user messages as literal text and left the agent-chat API, SSE payloads,
  SQLite schema and stored Message content unchanged.
- Disabled raw HTML, refused unsafe links and replaced Markdown images with
  non-loading alt text so model output cannot execute markup or fetch remote
  image resources.
- Added scoped typography, code, table, list, quote and responsive overflow
  styles inside existing assistant cards.
- Added component and ChatWorkspace regression coverage for persisted,
  streaming, plain-user-text and unsafe-content behavior.

## Verification

- Targeted Markdown and ChatWorkspace tests passed: 2 files and 17 tests.
- Full frontend Vitest, TypeScript typecheck and Vite production build passed.
- Dependency inspection reported the expected locked Markdown packages and no
  npm audit vulnerabilities.
- Browser verification covered the existing Markdown conversation at desktop
  and mobile width without horizontal page overflow or console errors.
- `git diff --check` passed.

## Public impact

This is a presentation-only frontend change. No backend, database, HTTP, SSE or
user-data format migration is required.
