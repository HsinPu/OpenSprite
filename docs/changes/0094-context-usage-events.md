# Context usage events

## Objective

Expose the backend's existing Context estimate and effective limit to the
frontend without adding a new event type, database table or request path.

## Changes

- Extend new `model.started` event payloads with `contextTokens`,
  `contextLimitTokens` and `inputBudgetTokens`.
- Calculate the estimate immediately before every main, tool-round and
  continuation model request using the existing conservative token counter.
- Validate the new values and their ordering in the SQLite Run-event boundary.
- Keep the original four-field `model.started` payload valid for replay of older
  runs.
- Teach the frontend event parser to accept both legacy and extended payloads;
  the indicator itself is added in the following slice.
- Document the additive event fields in the OpenAPI contract and agent-chat
  architecture.

## Public impact

The existing Run/SSE route and event type list are unchanged. New clients may
read the optional Context fields; clients that only understand the original
payload continue to receive the same required fields. No prompt content,
credentials, provider usage billing or raw model response is exposed.

## Verification

The backend contract, repository validation and Agent Loop regression tests are
updated in this slice. The next slice adds the visible frontend indicator.

## Remaining work

The browser indicator, i18n copy and responsive composer layout are implemented
in the following frontend slice.
