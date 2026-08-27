# 0048 General settings contract

## Objective

Add a strict local contract and persistence boundary for interface language and time-zone settings.

## Changes

- Added `GET/PUT /api/settings/general` with fixed locale and time-zone catalogs.
- Added strict schema-v1 atomic persistence at `.opensprite/config/general.json` and a dedicated `AppPaths` mapping.
- Composed the service into the system runtime with fail-closed defaults outside the lifespan.
- Added the authoritative OpenAPI document, exact route coverage and local-security tests.

## Public impact

The backend now exposes one additive General settings resource. Existing AI Settings, Provider and Agent Chat contracts and files are unchanged.

## Verification

- General settings, contract, path, runtime, application and local-security targeted tests passed.
- Backend source and tests compiled successfully.

## Remaining work

- The frontend does not consume the new resource until the next implementation slice.
