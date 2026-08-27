# 0046 Provider runtime composition boundary

## Objective

Separate Provider credential-lifecycle policy from concrete runtime construction without changing Provider behavior or public contracts.

## Changes

- Added `provider_runtime.py` as the owner of the Provider HTTP client, encrypted credential store, JSON state adapter, operation locks and native model gateway composition.
- Kept Provider protocols, sanitized errors, fail-closed behavior and transaction service in `provider_connections.py`.
- Added a narrow validator protocol so the transaction service no longer names the concrete HTTP validator type.
- Updated the system runtime and runtime-focused tests to import the factory from its new owner.
- Added an architecture guard that prevents concrete runtime construction from returning to the Provider policy module.

## Public impact

None. Provider HTTP/SSE contracts, credential encryption, metadata files, locks, rollback behavior, network requests and runtime lifecycle are unchanged.

## Verification

- Targeted Provider, runtime, AI-settings, Agent Chat and architecture tests passed.
- Backend source and tests compiled successfully.

## Remaining work

- AI-settings JSON persistence remains in its existing module because it is cohesive at the current scale.
