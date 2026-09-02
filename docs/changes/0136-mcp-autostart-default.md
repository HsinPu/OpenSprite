# MCP autostart default

## Objective

Enable the “start or connect when OpenSprite starts” switch by default when a
user creates a new MCP Server configuration.

## Changes

The empty MCP editor draft now starts with `startOnLaunch: true`. Editing an
existing Server still uses its persisted value, and users may turn the switch
off before saving.

## Public impact

Only newly created configurations through the settings UI receive the new
default. Existing saved Servers and the backend HTTP contract are unchanged.

## Verification

The MCP settings component test verifies both the enabled new-server default
and preservation of an existing disabled value. Frontend Vitest, typecheck,
production build, and `git diff --check` pass.

## Remaining work

No migration or bulk update of existing MCP Server records is performed.
