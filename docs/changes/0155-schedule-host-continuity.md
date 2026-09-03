# Schedule host continuity guidance

## Objective

Describe and detect when the host can keep the in-process scheduler alive
without granting OpenSprite authority to change operating-system policy.

## Changes

- Linux installation checks user lingering and prints the exact administrator
  command when it is disabled or cannot be confirmed.
- The installer does not invoke `sudo` or enable lingering.
- Windows documentation now states that scheduled Runs require user sign-in and
  a running OpenSprite process and cannot run through shutdown or sleep.
- Added deterministic runtime-status tests for Windows and Linux outcomes.

## Verification limitation

Linux helper syntax and static behavior are covered, but real Linux/systemd
execution remains intentionally deferred as previously agreed.
