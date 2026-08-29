# 0072 — Model context capabilities

## Outcome

- Added one backend-owned capability record for the supported direct-provider
  models.
- Replaced unverified fixed model identifiers with current provider model IDs.
- Extended OpenRouter model discovery with sanitized context-window and maximum
  output metadata.
- Kept dynamic model metadata in memory and HTTP responses only; no model cache
  or additional user-data file was introduced.

## Contract

OpenRouter model entries now include `contextWindowTokens` and nullable
`maxOutputTokens`. Both values are bounded positive integers, and a reported
maximum output may not exceed the model context window.

The fixed capability values were checked against the official OpenAI model
catalog and Anthropic model overview on 2026-08-29. OpenRouter field names and
semantics follow its official Models API.

## Verification

- Backend capability and OpenRouter discovery tests.
- Provider OpenAPI contract tests.
- Frontend provider client and settings tests.
- Frontend typecheck and build.
