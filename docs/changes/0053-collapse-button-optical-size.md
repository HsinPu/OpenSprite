# 0053 Collapse button optical size

## Objective

Remove the visible size mismatch between the left navigation and right Execution collapse controls.

## Changes

- Matched the sidebar button's grid centering to the Execution button.
- Increased the sidebar Ant Design icon from its inherited 14px size to the same 16px size used by the Execution control.
- Kept both controls at the existing 40px hit target with unchanged behavior and labels.

## Public impact

The two shell collapse controls now have matching outer and inner optical dimensions. No state, navigation or execution behavior changed.

## Verification

- Browser measurement confirmed both buttons are 40px, both icons are 16px and both use grid centering with 10px radii.
- All 93 frontend tests, TypeScript checks and the production build passed.

## Remaining work

- None for this visual mismatch.
