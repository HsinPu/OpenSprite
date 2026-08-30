# 0085 — Localize terminal Run errors

## Objective

Keep terminal Run errors in the user's selected interface language without
exposing the backend's internal message text.

## Changes

- Changed the terminal Run refresh path to translate the stable error code with
  the active frontend translator.
- Preserved the existing agent-chat HTTP payload and backend error envelope.
- Added an English-locale regression test that rejects raw backend error text.

## Verification

- Targeted `useConversationRun` tests passed.
- Full frontend Vitest, TypeScript typecheck and Vite production build passed.
- `git diff --check` passed.
