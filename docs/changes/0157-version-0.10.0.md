# Version 0.10.0

## Objective

Identify the first durable Agent scheduling release as OpenSprite 0.10.0.

## Changes

- Updated the authoritative backend package version and lock state to `0.10.0`.
- Updated app-info contract expectations and frontend version fixtures.
- Added README and architecture documentation for schedule behavior, safety,
  persistence, host continuity, and known notification limits.

## Public impact

Development and installed `/api/app-info` responses report `0.10.0` after the
new build is installed. This change does not update an existing installation.

## Verification limitation

Real Linux/systemd execution remains deferred; only helper syntax, deterministic
runtime detection, and documented behavior are verified on this Windows host.
