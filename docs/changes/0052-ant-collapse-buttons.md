# 0052 Ant Design collapse buttons

## Objective

Replace the two remaining custom shell collapse buttons with the project's existing Ant Design component system.

## Changes

- Replaced the sidebar collapse button with Ant Design `Button` and the official `LeftOutlined` or `RightOutlined` icon.
- Replaced the Execution panel collapse button and text glyphs with the same Button and icon system.
- Declared the already installed `@ant-design/icons` package as a direct, pinned frontend dependency.
- Preserved localized labels, expanded state, controlled region relationships, click behavior and responsive orientation.
- Standardized both controls at a 40px hit target with project color tokens.

## Public impact

The collapse controls now use consistent Ant Design rendering and icon geometry. Navigation, Execution state and public contracts are unchanged.

## Verification

- Component tests verify both controls render Ant Design button and icon classes.
- A clean lockfile install completed with zero reported vulnerabilities.
- All 93 frontend tests, TypeScript checks and the production build passed.
- Desktop and 390px browser checks confirmed 40px controls, official icons, responsive rotation and no horizontal overflow.
- The Vite service was restarted on `127.0.0.1:4173` and the updated page loaded successfully.

## Remaining work

- Other intentionally custom controls are unchanged.
