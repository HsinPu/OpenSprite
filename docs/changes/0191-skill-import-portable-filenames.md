# Portable Skill import filename limits

## Objective

Reject Skill package path segments that pass the character-count policy but
cannot be represented as a filename on the supported Linux filesystem boundary.
Version remains 0.14.0.

## Changes

- Extend the shared backend Workspace directory-name policy with a 255-byte
  UTF-8 limit. Workspace directory names, Skill directory names, and every
  imported supporting-file path segment now share this boundary.
- Mirror the same UTF-8 byte limit in the browser folder preview before upload.
- Cover the four-byte Unicode boundary explicitly: 63 emoji (252 bytes) remain
  valid and 64 emoji (256 bytes) are rejected.

## Public impact

No API shape or error code changes. Newly rejected folder imports continue to
use the existing `unsafe_path` response, and invalid Workspace directory names
continue to use `invalid_directory_name`.

## Verification

- Backend Workspace and Skill folder suites: 92 passed.
- Frontend Skill folder import suite: 15 passed.
- Frontend TypeScript typecheck passed.

## Remaining work

Real Linux filesystem and browser deployment verification were not performed.
The SymbolLattice guidance remains 0.511.0 while the installed CLI is 0.513.0,
and its existing index reports stale due to an indexer version change.
