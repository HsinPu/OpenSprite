# Version 0.10.1

## Objective

Identify the schedule-placement correction as OpenSprite 0.10.1 so installed
builds can be distinguished from the original 0.10.0 schedule release.

## Changes

- Updated the authoritative backend package version and lock state to `0.10.1`.
- Updated app-info contract expectations and frontend authentication fixtures.
- Ensured AuthGate tests unmount protected content before restoring the native
  fetch implementation, preventing late test-only requests.

## Public impact

Development and future installed `/api/app-info` responses report `0.10.1`.
This change does not update the currently installed application or push Git.
