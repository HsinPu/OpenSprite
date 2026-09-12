# Request and gateway attempt diagnostics

## Behavior

- A local traced gateway observes actual application-level gateway requests.
  It does not introduce retries or claim visibility into provider-internal HTTP retries.
- Main/tool-follow-up requests get different request IDs. Context-error retries
  retain the request ID and reference the preceding attempt ID.
- Continuation requests are distinct logical requests; each retry is a new attempt.
- Summary requests use compaction purpose and link to the compaction ID and the
  rejected parent request when applicable.
- Task-local context scopes keep simultaneous summaries isolated.
- Terminal records distinguish stream completion, failure, and cancellation.
  Missing provider usage is null, not zero. No raw content, credentials, or
  provider error messages are recorded.
- A diagnostics storage failure logs only run/attempt IDs and never replays the
  model request. The absent terminal record must remain unknown in the UI.
- Schema 18 adds the semantic model.attempt event. Existing semantic events remain
  supported and retain their original meanings.

## Verification

- Backend focused regression and contract suite: 93 passed.
- Frontend focused regression: 40 passed; TypeScript passed.
- Tests cover context retry identity/causality, tool-follow-up identity,
  unchanged continuation limits, cancellation, concurrent scope isolation,
  late provider usage, and metadata validation.

## Remaining goal

Phase 3 source receipts and phase 4 detailed/history/export UI remain pending.
Final full regression and browser validation remain required. No push, release
bump, or installed-runtime update was performed.
