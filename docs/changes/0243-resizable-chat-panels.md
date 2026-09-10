# Resizable chat panels and consistent sidebar actions (0.21.3)

## Scope

- Desktop left and right panels have independent pointer/keyboard resize separators.
- Left width: 220–600px (default 248px). Right: 260–800px (default 330px).
- Browser-local preferences survive reload and collapse. Viewport constraints reserve 360px for chat without overwriting preferred widths.
- Arrow keys move the divider by 10px; double-click or Home resets that side.
- At 900px and below, existing mobile drawers remain unchanged and resize separators are absent.
- New-chat and Workspace buttons share 44px height, 10px radius and a 10px vertical gap. Existing colors and external panel toggle positions remain unchanged.
- Release version 0.21.3; no backend behavior or user-data changes. Local installation is a separate operation.

## Verification

- Follow-up: expanded maximum widths to 600/800px; added a regression for large-screen widths, persisted values and constrained chat space.

- Frontend Vitest: 51 files, 429 tests passed, including five new sizing/storage/keyboard tests.
- Version 0.21.3 lockfile check (`uv lock --check --offline`) passed.
- Typecheck and production build passed. Existing large-chunk warning remains.
- Isolated browser fixture: real pointer drag changed left 248→348px and right 330→430px; both persisted across reload.
- At 960px viewport, both expanded panels left 360px for chat with no horizontal overflow; restoring viewport restored preferences.
- Double-click and Home restored 248/330px defaults.
- At 390px, no separators and no horizontal overflow.
- Browser measured both sidebar controls at 43.99px high with identical widths (subpixel rounding of 44px).
- Not a real backend/streaming test; the fixture uses mocked API responses and does not access product user data.
