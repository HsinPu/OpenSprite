# Compact Workspace settings

## Scope

- Move the Workspace title and creation/import toolbar into one responsive header.
- Use compact single-column cards with name, default/status tags, a truncated
  path and inline usage counts. Full paths are selectable in a hover/click
  popover, including keyboard activation and Escape dismissal.
- Keep empty mount sections to a single row. Existing mounts are expandable per
  Workspace ID; unavailable mount counts stay visible when collapsed. Successful
  mount saves expand the relevant list. No persisted expansion preference.
- Move managed Workspace edit/remove actions into an accessible overflow menu.
  Keep busy/non-empty deletion restrictions, explain disabled removal, preserve
  directory-retention confirmation and surface mutation errors. Default
  Workspaces do not receive an empty action menu.
- Preserve mount permission/path confirmations, backend contracts and existing
  editing flows. No dependency, API, storage or authorization changes.
- Add Traditional Chinese, English and Japanese labels. Maintain desktop/mobile
  wrapping, independent settings scrolling and focus restoration.

## Verification

- Full frontend regression suite: 52 files, 438 tests passed.
- Workspace component tests cover default immutability, blocked deletion,
  removal confirmation, mount creation and sensitive edits, collapsed errors,
  automatic expansion, empty mount rows and full-path dismissal.
- Typecheck and production build pass; existing bundle-size warning remains.
- Browser preview: 390x844, 768x900, 1366x768 and 1920x1080; no horizontal
  overflow in checked layouts. Cards measured approximately 176px high.
- Real UI edit/cancel and full-path popup checked without altering user data.
  Mount mutations use test mocks, not real user directories. Browser viewport
  override reset; 200% browser zoom was not separately exercised.
- No version bump, commit or installed-runtime update in this slice.
