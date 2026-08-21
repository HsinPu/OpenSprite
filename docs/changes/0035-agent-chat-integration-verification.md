# 0035 — Agent chat integration verification

## Scope

Final verification of the run-centric Agent chat implementation across the
browser, local HTTP/SSE boundary, Python runtime, Provider adapter, SQLite
persistence, and responsive UI.

## Automated evidence

- Backend: 336 pytest cases passed with warnings treated as errors.
- Backend: source and tests compiled successfully; `uv lock --check --offline`
  and `uv pip check` passed with 25 compatible packages.
- Frontend: a clean `npm ci --ignore-scripts` installed 170 packages with zero
  reported vulnerabilities.
- Frontend: 77 Vitest cases, TypeScript type checking, and the Vite production
  build passed.
- Repository: `git diff --check` passed, the worktree was clean, and CodeGraph
  reported its 85-file index up to date.

## Live browser evidence

- A real `openrouter/auto` Run using the persisted `default` response mode
  streamed text, completed, created the assistant Message, updated the sidebar,
  and remained visible after a full page reload.
- The execution panel displayed the real Provider/model/mode snapshot, five
  persisted semantic events, and correctly reported that no extra tool was
  used by the intentionally empty production Tool Registry.
- Browser logs contained no warning or error after the final frontend/backend
  restart.
- At a 1422px browser viewport, the expanded layout had no horizontal overflow;
  collapsed sidebar and execution-panel widths were approximately 76px and
  68px.
- A same-origin 390px iframe verification had matching 390px client and scroll
  widths, a stacked chat layout, a working mobile navigation drawer, and a
  working collapsed/expanded execution panel.

## Review outcome

The diff-first frontend review found and corrected one terminal-event race:
SSE now closes and the Run leaves its active state before the final durable
refresh, so a transient refresh failure cannot leave a completed Run appearing
active. Live verification then found and corrected OpenRouter's repeated,
identical terminal finish reason. No remaining actionable finding was found in
the reviewed Agent chat path.

Live OpenAI and Anthropic generation were not exercised because this acceptance
run used the currently selected OpenRouter connection. Their native request and
stream behavior remains covered by mock transport tests. Installer execution is
still outside this project stage and has no committed runtime tests.
