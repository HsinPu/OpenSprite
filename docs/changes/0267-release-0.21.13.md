# Release 0.21.13

- Synchronize backend package metadata, lockfile and README to 0.21.13.
- Include schedule settings improvements recorded in change 0266.
- No dependency or backend execution-policy changes.
- Implementation verification: 482 frontend tests passed; final focused suite
  passed 22 tests, followed by successful typecheck and build.
- Desktop preview inspected. Mobile and 200% zoom visual checks remain outstanding.
- Version metadata checked with `uv lock --check --offline` and `git diff --check`.
- No push or local installation update.
