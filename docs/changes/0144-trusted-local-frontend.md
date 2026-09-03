# Trusted local frontend

## Objective

Enter the existing application directly when the installed access policy trusts
the local desktop, without presenting password-only actions.

## Changes

- Extended strict frontend authentication parsing with `trusted_local`.
- Made `AuthGate` mount the application directly in trusted-local mode while
  retaining the existing password Session lifecycle.
- Hid sidebar logout and password mutation controls when authentication is not
  enabled.
- Added a localized Privacy explanation of the same-OS-account trust boundary
  in Traditional Chinese, English, and Japanese.

## Public impact

Trusted-local installations open directly after the public authentication
status check. Password-protected installations retain their existing behavior.

## Verification

- AuthGate trusted-local component coverage.
- Privacy mode presentation and password-action absence coverage.
- Existing password setup, login, expiry, password change, and logout tests.
- TypeScript typecheck.

## Remaining work

Installers must explicitly select and persist the installation mode.
