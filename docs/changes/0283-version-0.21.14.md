# Version 0.21.14

- Bump the authoritative backend package version and its lockfile entry from
  0.21.13 to 0.21.14.
- Includes the diagnostic UI hierarchy update documented in 0282: heading icon,
  compact event list, usage and technical disclosures, incremental history and
  secondary export action.
- No dependency upgrades, backend behavior changes, commit, push or local
  installation are part of this version-only change.

Verification: `uv lock --check --offline` passed (46 packages); `git diff --check`
passed. Package and lockfile diffs contain only the product version change.
