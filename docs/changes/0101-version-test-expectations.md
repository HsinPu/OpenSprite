# Version test expectations

## Objective

Keep the build-info regression tests aligned with the authoritative `0.2.1`
package version introduced by the preceding version bump.

## Changes

- Update only successful app-info and build-info expectations from `0.2.0` to
  `0.2.1`.
- Preserve malformed and mismatched build-metadata cases as fail-closed tests.

## Public impact

None. The product version remains `0.2.1`; runtime and API behavior are
unchanged.

## Verification

- Full backend pytest suite.
- Backend compileall, offline lock check, and dependency check.
