# 0018 Align credential instructions

## Objective

Align repository-level agent guidance with the committed encrypted local
credential architecture.

## Changes

- Replaced the obsolete OS credential-service rule with the AES-256-GCM
  `auth.json` and per-install `credential.key` policy.
- Documented plaintext, fixed-key, keyring fallback, multi-process and complete
  `.opensprite` exposure boundaries.
- Updated backend ownership and verification commands to match the current
  runnable frontend, Python backend and committed test suites.
- Kept installer verification explicitly unavailable until installer tests are
  implemented.

## Public impact

None. This changes repository instructions only; runtime code, persisted data
and public API contracts are unchanged.

## Verification

- Confirmed every documented path and command has a current repository owner.
- Confirmed the obsolete OS keyring rule no longer appears in `AGENTS.md`.
- Ran `git diff --check` and inspected the final worktree.

## Remaining work

- Clean-install Linux ACL and future installer execution tests remain outside
  this documentation-only correction.
