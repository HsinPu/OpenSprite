# 0082 — Mobile sidebar surface cleanup

## Objective

Remove compact-navigation background bleed and header overlap without changing
desktop navigation behavior.

## Changes

- Positioned the compact sidebar below the fixed 60px application header.
- Replaced the inherited translucent desktop sidebar surface with the opaque
  application surface token on compact layouts.
- Hid the duplicated sidebar brand row because the fixed compact header already
  owns the OpenSprite identity.
- Reduced compact sidebar padding to `18px 16px`, making the new-conversation
  action the first visible menu item.
- Started the dismissal backdrop below the fixed header while preserving its
  existing opacity and close behavior.

## Public impact

No API, persistence, navigation state or desktop layout contract changed. The
compact sidebar remains a left-side disclosure controlled by the existing
hamburger button.

## Verification

- Full frontend Vitest passed: 17 test files and 148 tests.
- TypeScript typecheck and Vite production build passed. Vite retained its
  existing bundle-size warning.
- Installed-runtime browser verification covers the compact open-menu state,
  opaque surface, header separation, backdrop boundary and close interaction.
- Browser measurements confirmed the sidebar and backdrop begin at 60px, the
  sidebar background resolves to opaque white, the duplicate brand row is not
  displayed, and the new-conversation action begins at 78px. Clicking the
  remaining backdrop closes the menu normally.

## Remaining work

- None for this UI slice.
