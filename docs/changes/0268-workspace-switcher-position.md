# Workspace switcher popup positioning

- Reproduced an open workspace menu rendered at negative offscreen coordinates
  in the installed browser. Workspace data was present.
- Anchor the Ant Design popup within the positioned workspace-switcher wrapper,
  with explicit bottom placement, matching width and bounded scrolling. This
  follows the existing user-menu positioning approach.
- Changing only the popup container, or replacing the trigger with a native
  button, did not fix the browser failure; retain the original Ant Design Button.
- Add integration coverage proving that the menu is mounted inside the switcher
  and that its create-workspace action still works.
- Desktop preview: popup at x=16, y=172, width=215 rather than negative coordinates.
- Reopening after sidebar collapse retains the correct popup coordinates.
- Verification: 32 App integration tests, typecheck, build and diff checks passed.
  Existing production bundle-size warning remains; mobile visual testing not performed.
- No workspace data, API, version or installed application changes.
