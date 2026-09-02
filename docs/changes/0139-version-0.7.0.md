# Version 0.7.0

## Objective

Identify the expanded output-continuation policy and schema-v10 migration as
OpenSprite 0.7.0.

## Changes

The authoritative backend version, lockfile, application contract, app-info,
and build-info expectations now use `0.7.0`.

## Public impact

New installations and updates report version `0.7.0` through `/api/app-info`
and the About settings view.

## Verification

Version contract tests, offline lock validation, and package consistency checks
pass with the same value.

## Remaining work

Publishing and updating the installed desktop runtime remain separate explicit
operations.
