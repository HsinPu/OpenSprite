# 0071 Ant execution chevron

## Objective

Align the execution-record disclosure icon with the existing Ant Design icon
system without changing native disclosure behavior.

## Changes

- Replaced the Unicode `⌄` character with `DownOutlined` from
  `@ant-design/icons`.
- Kept the semantic native `details` / `summary` interaction and keyboard flow.
- Rotated the Ant icon 180 degrees while the execution record is open; existing
  reduced-motion rules continue to suppress the transition when requested.

## Verification

- ChatWorkspace regression coverage confirms the Ant icon is rendered and the
  old Unicode character is absent.
- Full frontend verification passed: 15 test files and 128 tests, TypeScript
  typecheck and the Vite production build.
