# User menu positioning

- Remove the decorative upward arrow from the user trigger; preserve the full-row menu interaction and expanded accessibility state.
- Give the popup an opaque existing surface color, a token-based border/radius and a soft outer shadow so it reads as a separate panel without changing the palette. Keep the eight-pixel separation and remove the clipped inner menu shadow.

- Anchor the dropdown to the positioned utility navigation container and explicitly place it above the trigger, with bounded scrolling and sidebar width.
- Remove automatic focus during initial alignment; retain menu Escape handling and settings return focus.
- Browser verification on the development runtime: menu bounds x=16, y=519, width=215, height=113 at 1280x720; a real pointer click opened General settings.
- Typecheck and two component tests passed. Installed runtime has not been updated; mobile viewport verification remains pending.
