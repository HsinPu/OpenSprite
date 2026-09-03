# README access guide

## Objective

Document the complete local-trust and password-login workflows in the root
README for Windows, Ubuntu Desktop, and remote Linux users.

## Changes

- Added access-mode selection, password/session behavior, setup expiry, reset,
  mode switching, and data-preservation guidance.
- Added the remote Linux SSH Tunnel and `/dev/tty` bootstrap workflow.
- Documented the trusted-local threat boundary and password-mode nonclaims.
- Corrected stale statements that said the Linux installer was not implemented.

## Public impact

Repository users can select and recover the correct access mode without first
reading implementation-specific architecture documents.

## Verification

- Cross-checked commands and terminology against current Windows/Linux
  installer sources and the authentication architecture.
- Markdown link, heading, command, diff, and repository-state inspection.

## Remaining work

The README continues to state that real Linux/systemd isolation execution is
deferred until a Linux host is available.
