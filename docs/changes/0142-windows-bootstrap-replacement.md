# Windows bootstrap replacement

## Objective

Allow `-ResetLocalAccess` to atomically replace an existing bootstrap record on
Windows.

## Changes

- Replaced the invalid empty `File.Replace` backup argument with a unique
  same-directory backup path.
- Delete the temporary backup after replacement without exposing either the
  raw bootstrap token or its prior hash.
- Extended the Windows installer isolation test to generate two consecutive
  bootstrap records and verify replacement plus unrelated-data preservation.

## Public impact

Running the installer with `-ResetLocalAccess` now succeeds when an expired or
unused `state/access-bootstrap.json` already exists.

## Verification

- Reproduced the previous `.NET File.Replace` empty-path exception during a
  real local reset.
- Passed the Windows installer isolation test with consecutive bootstrap
  generation.
- Re-ran the real 0.8.0 reset and verified health, setup-required state, a new
  unexpired 30-minute record, and preserved SQLite and credential files.

## Remaining work

The one-time raw token remains intentionally unrecoverable after the installer
opens the setup URL. A lost or closed setup URL requires another explicit
`-ResetLocalAccess` run.
