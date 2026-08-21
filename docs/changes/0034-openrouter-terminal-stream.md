# 0034 — OpenRouter terminal stream compatibility

## Objective

Complete real OpenRouter Agent Runs when the Provider repeats the same terminal
finish reason in its final usage-bearing stream chunk.

## Root cause

A live `openrouter/auto` response emitted complete text, then sent
`finish_reason: "stop"` once in the terminal choice and again in the final
usage-bearing choice before `[DONE]`. The strict adapter rejected every repeated
finish reason, so the Run was recorded as `invalid_provider_response` after its
text had already arrived.

## Change

- Accept a repeated finish reason only when it is a string identical to the
  previously observed value.
- Continue to reject missing completion, conflicting repeated values, unknown
  terminal reasons, malformed choices, and incomplete streams.
- Keep reasoning fields, upstream bodies, credentials, and diagnostic content
  out of logs and persistence.

## Verification

- A regression fixture mirrors the observed terminal choice followed by an
  identical usage-bearing terminal choice.
- A separate negative fixture proves conflicting repeated values still fail
  closed.
- The full backend and frontend suites, static compilation, lock checks, build,
  and a second live browser Run are required before completion.
