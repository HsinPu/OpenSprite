# 0204 — Skills simple enable policy (0.16.0)

- Remove the manual content-version approval gate. New save/ZIP import starts
  enabled; existing record updates preserve its toggle. Scan remains disabled.
- Settings cards show only an enable switch and archive/remove action.
  Creation/import preview remains, with no edit/approval flow for existing cards.
- An enabled valid external edit is visible to the next Run, while existing
  immutable snapshots retain their content. Invalid/missing/unsafe files fail closed.
- Catalog v2 migration preserves disabled records and disables previously pending
  valid records. Atomic failure leaves v1 intact and ordinary chat available.
- Keep legacy confirmedHash storage/response metadata inert for persisted record
  and journal compatibility; reject it in the strict enable request.
- Update locales, API contract, README, architecture and product version 0.16.0.
- No commit, push or installed-application update is included.

Verification: backend 821 passed / 3 skipped with warnings treated as errors
(existing cache ownership restriction bypassed with no:cacheprovider);
frontend 330 passed; typecheck, production build, compileall, offline lock and
dependency checks passed. Windows installer isolation passed with native-binary
quarantine warnings. No real-browser or Linux GUI/systemd verification claimed.
