# Output continuation option order

## Objective

Keep the continuation selector in a deliberate policy order rather than
JavaScript's integer-like object-key order.

## Changes

- Define the selector values explicitly as off, 1, 2, 3, 5, and unlimited.
- Preserve the existing setting values, labels, persistence, and backend
  behavior.

## Verification

- Settings component test, TypeScript typecheck, and production build.
- Installed-browser verification of the rendered option order.
