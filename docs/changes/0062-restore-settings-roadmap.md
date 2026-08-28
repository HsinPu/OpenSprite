# 0062 Restore the settings roadmap

## Objective

Keep unfinished settings visible as a product roadmap without restoring fake
interactive state.

## Changes

- Restored Memory and data, Tools and connections, Appearance, Privacy and
  About as disabled Demo navigation categories.
- Restored planned startup, conversation, send behavior, notification,
  automatic model and model-name preferences as non-interactive future rows.
- Kept all unfinished items visibly distinct from persisted controls and
  omitted every checkbox, select or replacement state for them.
- Increased the General dialog height to accommodate the roadmap while keeping
  independent content scrolling and full-screen mobile behavior.

## Public impact

No HTTP contract, persistence behavior or executable setting changed. Language,
time zone, Provider, model and response mode remain the only working settings.

## Verification

- Settings component tests for disabled Demo categories, future rows and the
  absence of fake checkboxes.
- Complete frontend tests, TypeScript typecheck and production build.
- Desktop and mobile browser checks for hierarchy and overflow.
