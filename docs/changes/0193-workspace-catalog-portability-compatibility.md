# Workspace catalog portability compatibility

## Objective

Preserve Workspace catalogs created before the portable UTF-8 segment limit
while keeping that limit on every newly accepted Workspace or Skill path.
Version remains 0.14.0.

## Changes

- Separate strict new-directory validation from persisted catalog validation.
- Keep the 255-byte UTF-8 limit for newly created or imported Workspace names
  and Skill package path segments.
- Allow existing version 2 and version 3 Workspace catalogs to retain and
  rewrite directory names that satisfied the earlier 80-character policy.
- Add a regression covering an existing 64-emoji directory name, which is 256
  UTF-8 bytes and was accepted before the portable limit was introduced.

## Public impact

Upgrading no longer makes the backend unavailable solely because an existing
Workspace directory name exceeds the new portable UTF-8 byte limit. New names
remain subject to the stricter cross-platform rule.

## Verification

- The regression test failed with `WorkspaceStoreError` before the fix.
- Persisted-catalog compatibility, new Workspace validation, and Skill package
  path validation focused tests: 3 passed.

## Remaining work

The broader backend suite and real Linux filesystem behavior still require
verification. SymbolLattice guidance is 0.511.0 while the installed CLI is
0.513.0; the current repository index was fresh during this change.
