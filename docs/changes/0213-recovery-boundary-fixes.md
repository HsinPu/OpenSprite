# Recovery boundary fixes

Status: complete. Three accepted findings: ambiguous submission identity,
terminal hydration recovery, and budget-adaptive Skill discovery.

The discovery regression first failed with `context_limit` despite sufficient
space for fewer entries. The Skill phase now reduces its response until it fits,
never below one item, and recalculates nextOffset from the actual returned count.
The snapshot and loaded instructions remain unchanged.

Terminal hydration now retains a separate pending flag so terminal business
status does not suppress the existing bounded retry policy. Successful recovery
does not reopen a terminal stream and preserves a model failure as a business
error rather than repeatedly retrying it. A regression simulates a completed
event followed by temporary GET failures and verifies automatic message recovery.
An explicit recovery epoch handles React batching when failures settle immediately.
The bounded retry regression verifies three attempts and no requests afterward.

Submission reconciliation now reuses the complete pending request, not just its
ID when text happens to match. A changed draft returns false after reconciliation
so the composer does not clear unsent edits. Known initial request rejections
release the pending identity; ambiguous failures retain it. A lost-response test
asserts both POST bodies remain identical after editing. Tests also check the
false return preserving edited drafts and fresh content after definitive rejection.
All 17 hook tests and 8 backend Skill tests pass. Typecheck and production build
pass (the existing bundle-size warning remains). A parallel full frontend run
passed 358 tests but timed out in the existing Skills pagination test; a serial
rerun passed all 43 files / 359 tests. Compileall and git diff --check passed.
No live model or installed-runtime claim is made.

No installation, commit or push is part of this task.
