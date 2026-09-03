# Windows access mode selection

## Objective

Let Windows desktop installations explicitly use trusted-local access while
preserving password protection across existing upgrades.

## Changes

- Added `-AccessMode TrustedLocal|Password` and persisted the selected strict
  access policy atomically.
- Made new Windows installs default to trusted-local access; existing access,
  bootstrap, or policy state is preserved as password-required unless changed
  explicitly.
- Trusted-local installs remove unused bootstrap state, preserve password hash,
  and open the base local URL.
- Added rollback restoration for previous policy and bootstrap bytes.
- Extended isolation coverage for policy replacement and explicit trusted-local
  installation.

## Public impact

Windows local desktop users can open OpenSprite without a password. Existing
0.8 installations do not silently change mode.

## Verification

Windows installer parsing and full isolated installation test, including
strict policy persistence and preserved unrelated data.

## Remaining work

Linux mode selection and remote terminal bootstrap delivery are separate.
