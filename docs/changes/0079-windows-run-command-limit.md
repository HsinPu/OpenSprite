# 0079 — Windows Run command limit

## Objective

Make the installed OpenSprite runtime start reliably at Windows logon without
adding a Scheduled Task or another launcher format.

## Changes

- Reproduced the failed logon start with a healthy installation, a recognized
  current-user Run entry and no listener on port 8765.
- Confirmed the previous Run command was 282 characters, beyond Windows'
  documented 260-character limit.
- Preserve the absolute Windows PowerShell and launcher paths while omitting
  redundant official install-root and port arguments. Non-default values remain
  explicit.
- Reject installation before registry mutation if a generated Run command
  exceeds 260 characters.
- Added an isolated regression check for the official command shape and length.

## Public impact

The installed program path, user-data root, HTTP API, startup name and port are
unchanged. Existing installations receive the shorter Run value on the next
installer update. No Scheduled Task, CMD/VBS shim or compatibility path was
added.

## Verification

- Windows installer isolation test passed, including build, installed Python
  import, command-length regression and uninstall.
- The official generated Run value measured 212 characters.
- A live installer update wrote the 212-character value, preserved
  `.opensprite` and its SQLite database, and returned health `ok` on port 8765.
- The installed `install.ps1` hash matches the repository source.

## Remaining work

The next real Windows logon is the final external trigger verification. Windows
may temporarily retain old rollback or isolated native-module files while its
security scanner holds them open.
