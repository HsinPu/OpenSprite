# Local access policy

## Objective

Add an installation-owned policy that can explicitly select trusted local
access without weakening the existing password-required default.

## Changes

- Added strict atomic `config/access-policy.json` persistence with
  `trusted_local` and `password_required` modes.
- Added the `trusted_local` authentication-status variant and safe
  `authentication_not_enabled` error.
- Made production composition skip only Session middleware in trusted-local
  mode while retaining Host, Origin, and response-security middleware.
- Made missing policy default to password protection and malformed policy fail
  closed with a safe `503 access_store_unavailable` response.

## Public impact

`GET /api/auth/status` can now return `{"state":"trusted_local"}`. Password
mutations are unavailable in that mode. Installers do not select the new mode
until their platform-specific slices are delivered.

## Verification

- Backend authentication, runtime-composition, and contract tests.
- Explicit tests for strict persistence, missing-policy default, trusted-local
  Session bypass, retained Origin rejection, and malformed-policy fail-closed.

## Remaining work

Frontend mode-aware presentation and Windows/Linux installer selection are
delivered in following slices.
