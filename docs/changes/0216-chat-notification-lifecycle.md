# Isolate chat notification callbacks

The locale-dependent parent refresh callback changed refreshTerminal and watchRun,
which reset pending request identity. Read the current notification callback from
a ref instead of making it a lifecycle dependency. Notifications still invoke
the latest parent callback.

Regression: the test parent callback now changes with locale. Before the fix,
retry submitted edited text instead of the original request. After the fix all
43 frontend files / 360 tests pass, including this regression. Typecheck,
production build and git diff --check pass. Existing bundle warnings remain.
No live browser verification is claimed.
No version bump, installation, commit or push.
