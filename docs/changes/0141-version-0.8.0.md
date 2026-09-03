# Version 0.8.0

## Objective

Identify the mandatory local-authentication release as OpenSprite 0.8.0.

## Changes

- Updated backend package metadata and lock state to `0.8.0`.
- Updated application-info and build-info expectations.
- Added the pinned Argon2 implementation dependency.

## Public impact

`/api/app-info` and installed `build-info.json` report version `0.8.0`.

## Verification

Backend metadata/contract tests, lock validation, installed-runtime checks, and
the Windows installer isolation test are used as release gates.

## Remaining work

This record does not create a hosted release or publish an installer artifact.
