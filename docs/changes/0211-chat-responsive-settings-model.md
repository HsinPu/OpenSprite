# 0.18.2 Chat layout and settings-only model selection

- Removed the chat composer model selector. Settings remains the model selection entry point; Run submission continues to use backend AI settings.
- Current and historical execution panels display the actual Run model.
- At widths up to 1200px, execution details use the existing Drawer. Navigation retains its 900px breakpoint.
- Composer controls use explicit grid placement; narrow containers place Context above the action row.
- Preserved existing draft state and scheduled execution profile behavior. Resizing to desktop closes the compact Drawer without clearing the draft.
- Keyboard submit respects the same loading/settings-saving guard as the send button.

## Verification

- Frontend typecheck, production build, and all 351 tests in 43 files passed, including 22 ChatWorkspace tests and settings-only model selection regressions.
- Backend Run service, scheduler, version/application contract tests: 50 passed (cache provider disabled to avoid the local cache permission warning).
- Offline uv lock and dependency checks passed. SymbolLattice reported fresh.
- Production bundle size warning remains unchanged in scope.
- Isolated browser checks used the real ChatWorkspace and application CSS with deterministic hook substitutes, not the installed backend. Actual CSS widths 320, 390, 767, 982, 1200, 1201, and 1440 had no document horizontal overflow. Composer/send geometry remained within the viewport. A 300-character draft survived resizing, sidebar collapse, and settings-model prop change; the displayed Run model stayed original. Compact Drawer opened at mobile/medium widths and closed on desktop resize. Browser viewport override was reset afterward.
- The fixture is not a full live-provider or installed-application test. No real model request, OS mobile keyboard, or Linux GUI test was performed.
- No commit, push, or local installation performed.

## Repeat the isolated browser check

From `frontend`, run `node node_modules/vite/bin/vite.js --config tests/browser/chat.config.mjs`, then open `http://127.0.0.1:8877/tests/browser/chat.html`. This dedicated config substitutes chat transport hooks and has no API proxy. Verify actual `innerWidth` when the browser has a non-default zoom. The fixture is excluded from the production entry point.
