# Access reset rollback

## Objective

Preserve the previous password hash when a Windows or Linux reset installation
fails after access state begins changing.

## Changes

- Added `access.json` to Windows installer rollback capture and restoration.
- Added `access.json` to the Linux protected state-backup directory and rollback
  restoration.
- Kept successful reset behavior unchanged: the old hash is removed only when
  the complete installation succeeds.

## Public impact

A failed reset no longer risks leaving a previously configured installation
without its old password hash.

## Verification

Windows installer isolation, Linux helper tests, Bash syntax, and final source
inspection.

## Remaining work

Linux systemd rollback still requires operational execution on a real Linux
host before release qualification.
