# 0023 Settings select popup layer

## Objective

Keep provider and model selection menus visible and interactive above the
native settings dialog.

## Changes

- Rendered both Ant Design Select popup menus inside the settings surface
  instead of the document body.
- Preserved the existing provider/model values, model discovery, search,
  persistence, and HTTP contracts.
- Added a regression test proving both popup menus remain descendants of the
  settings surface.

## Verification

- Confirmed the regression test fails when the popup is portaled outside the
  settings surface and passes after the container correction.
- Browser verification confirmed the OpenRouter model menu is visibly layered
  above the settings dialog and remains ready for user selection.
- Frontend unit tests, TypeScript, production build, and repository checks are
  recorded with the implementation commit.
