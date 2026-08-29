# 0063 Keep provider removal confirmation in dialog

## Objective

Make the Provider removal confirmation visible and operable inside the native
Settings dialog.

## Changes

- Mounted the Ant Design Popconfirm inside the Settings surface instead of the
  document body.
- Preserved the existing confirmation copy, DELETE request, busy state,
  fallback model selection and stale OpenRouter response handling.
- Added a regression assertion that the Popconfirm belongs to `.settings-page`.

## Public impact

Provider HTTP contracts and credential deletion behavior are unchanged. The
confirmation is now in the native dialog top layer and can be operated before
any destructive request is sent.

## Verification

- Focused Provider disconnect component test.
- Complete frontend tests, TypeScript typecheck and production build.
- Browser verification opens and cancels the confirmation without deleting a
  stored credential.
