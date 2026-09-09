# Chat draft and locale lifecycle

Move the controlled composer draft to App, keyed by workspace, conversation and
new-chat revision. Accepting a new conversation transfers unsent edits to its
real ID; matching submitted content is cleared. Other destinations do not show
the previous draft. Late setters from the previous component cannot clear edits.

Keep the hook translator callback stable while reading the current translator,
so locale changes do not reset pending request identity or recovery state.

Verification: 43 frontend test files / 360 tests passed, including the actual App
acceptance/remount and new-chat isolation path, and locale switching between an
ambiguous POST and retry. Typecheck, production build and git diff --check passed.
The existing bundle-size warning remains. Browser interaction was not exercised.
SymbolLattice refused stale evidence after indexer-version-changed; direct current
source was used instead, without rebuilding or upgrading the index/tool.
No version bump, installation, commit or push.
