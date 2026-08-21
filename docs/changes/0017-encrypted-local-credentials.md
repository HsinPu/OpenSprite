# 0017 Encrypted local credentials

## Objective

Store provider API keys below the OpenSprite user-data root in one
cross-platform encrypted format without requiring a startup password.

## Changes

- Added `AppPaths` mappings for `.opensprite/auth.json` and
  `.opensprite/config/credential.key`.
- Added a strict AES-256-GCM credential store with a random per-install key,
  unique nonces, authenticated provider metadata, bounded reads, fsync and
  atomic replacement.
- Provider listing now checks encrypted-entry fingerprints without decrypting
  API keys. Provider validation, model discovery and rollback decrypt only when
  the secret is required.
- Removed the OS keyring adapter and dependency. Existing Credential Manager or
  Secret Service entries are not read or migrated.
- Preserved the HTTP contract, frontend payloads, validate-before-save,
  Provider metadata schema v2 and failure rollback behavior.

## Public impact

Provider credentials move from the operating-system keyring to encrypted files
inside `.opensprite`. An isolated `auth.json` is unusable without
`credential.key`; possession of the entire `.opensprite` root is sufficient to
decrypt it. Backup, restore and deletion must keep both files together.

## Verification

- Focused encrypted-store, AppPaths, Provider service and runtime tests: 80
  passed.
- Full backend tests: 234 passed with warnings treated as errors; bytecode
  compilation passed.
- Offline lock and dependency checks passed with 25 compatible packages.
- Full frontend tests: 45 passed; TypeScript checking and production build
  passed with the existing bundle-size advisory.
- CodeGraph, source scan, `git diff --check`, worktree and runtime smoke checks.
- Independent Sol/high security review found no P0-P2 issue. Its one P3 stale
  OpenAPI description was corrected and approved in targeted re-review.

## Remaining work

- Clean-install ACL verification on Linux remains an installer acceptance gate.
