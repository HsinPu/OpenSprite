# Subagent execution error pagination

- Separate a successful result response's execution error from request/transport errors in frontend result state.
- Failed child executions keep their diagnostic visible while allowing all saved output pages to load. Only request failures show a request retry action.
- Add a regression with a failed 4,000-character first page, a second-page network failure, and a successful second-page retry without duplicated text.
- Targeted SubagentExecution tests and production build (including TypeScript check) passed. Existing chunk-size warning remains; no browser fault injection or backend changes.
- Version remains 0.20.3. No commit, push, or local installation performed.
