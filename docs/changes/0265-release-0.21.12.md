# Release 0.21.12

- Synchronize backend package metadata, lockfile and README from 0.21.11 to 0.21.12.
- Include the Agents settings layout and discovery improvements documented in change 0264.
- No dependency, backend API, inheritance or execution-policy changes.
- Implementation verification: 467 full-suite frontend tests passed, followed by 21 passing Agents tests after two additional regression cases; typecheck and build passed.
- Desktop preview verified; exact mobile viewport and 200% zoom remain unverified as recorded in change 0264.
- Release metadata verification: `uv lock --check --offline` and `git diff --check` passed.
- Version update only. No commit, push or local installation requested.
