# Version 0.6.0

## Objective

Identify the native local path-picker release as OpenSprite 0.6.0.

## Changes

The authoritative backend version, lockfile, application contract, app-info,
and build-info expectations now use `0.6.0`.

## Public impact

New installations and updates report version `0.6.0` through `/api/app-info`
and the About settings view.

## Verification

Version contract tests, offline lock check, package build, and Windows installer
isolation verify the same value.

## Remaining work

Publishing and updating the currently installed desktop runtime remain separate
explicit operations.
