# Response delivery setting

## Objective

Let users choose whether assistant text is rendered incrementally or shown as
one completed response, with streaming as the default.

## Changes

- Add strict AI-settings `responseDelivery` values `stream` and `complete`.
- Upgrade the persisted settings document to schema-v8; schema-v7 and earlier
  reads default the new field to `stream` without rewriting.
- Add localized settings UI labels and descriptions for all supported locales.
- Keep Provider HTTP requests, Run SSE events, execution records, Context,
  continuation, cancellation and Prompt logging unchanged.

## Verification

- Backend settings round-trip, strict schema, migration and API tests.
- Frontend settings client, selector and App integration tests.
