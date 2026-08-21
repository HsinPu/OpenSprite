# 0019 Persist model selection backend

## Objective

Persist a selected Provider/model as a real local preference without adding
model execution or storing any secret or dynamic model catalog.

## Changes

- Added `contracts/model-selection.openapi.json` for `GET` and `PUT
  /api/settings/model`, with a strict `{providerId, modelId}` selection or
  `null` to clear it.
- Added strict schema-v1 persistence at
  `.opensprite/config/settings.json`. Missing-file reads are side-effect free;
  successful writes use fsync and atomic replacement; clearing the only setting
  removes the file.
- Added backend composition, local-origin-protected routes, connected-provider
  validation, and a separate model-selection error schema so settings-only
  errors do not appear in provider API OpenAPI models.
- Kept the saved value limited to identifiers. Display labels and OpenRouter
  dynamic model lists remain outside this store.

## Public impact

The local API gains `GET` and `PUT /api/settings/model`. The user-data root may
now create `config/settings.json` after a successful model selection. It
contains no API key, credential fingerprint, display label, or provider model
list. Existing Provider connection requests and payloads remain unchanged.

## Verification

- Full backend pytest suite: 255 passed with warnings treated as errors.
- Backend bytecode compilation, offline lock check, and dependency check:
  passed; 25 installed packages are compatible.
- Contract JSON parsing, `git diff --check`, and CodeGraph status: passed.

## Remaining work

- The frontend consumer, model labels, fallback UI, and chat execution remain
  separate slices.
