# Agent result retry and description validation

## Changes

- Preserve displayed subagent result pages when a later page fails. Store the failed request's offset and append mode, and retry that page without restarting or duplicating previous text.
- Require a nonblank Agent description in both the editor save guard and button state. Mark the description field required for visual and assistive-technology users.
- Add regressions for failed-page retry and whitespace-only descriptions.

## Scope

Verification: 47 frontend test files / 408 tests passed; production build (including TypeScript check) and git diff check passed. Existing build chunk-size warning remains.

- Frontend only; backend contracts remain unchanged.
- Version remains 0.20.3. No commit, push, or installed-runtime update requested.
- No real browser/network fault injection performed.
