# Version 0.6.1

## Objective

Identify the MCP autostart-default adjustment as OpenSprite 0.6.1.

## Changes

The authoritative backend version, lockfile, application contract, app-info,
and build-info expectations now use `0.6.1`.

## Public impact

New installations and updates report version `0.6.1` through `/api/app-info`
and the About settings view.

## Verification

Version contract tests, offline lock validation, and package consistency checks
pass with the same value.

## Remaining work

Publishing and updating the installed desktop runtime remain separate explicit
operations.
