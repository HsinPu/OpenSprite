# Compact diagnostic layout

## Changes

- Removed generic failure heading; retained safe error and actionable credential guidance.
- Suppress duplicate error prose only for one fully loaded operation belonging to the failed run with the same structured error code. Multiple attempts retain their individual errors.
- Replaced usage descriptions with semantic definition lists: aligned narrow rows and three columns above 600px of container space. Actual and estimated usage remain separate; missing is not zero.
- Reduced disclosure spacing, removed outer rounded record styling, and renamed context receipt to request usage estimate in all three locales.
- Moved history scope/export description into the More menu's controlled Popover. Opening focuses its close button; Escape closes only the explanation and returns focus. No hover-only disclosure.
- Existing resizing, event grouping and safe raw export unchanged. No dependency, version, commit or deployment changes.

## Verification

- Initial 15 existing focused tests passed; new duplicate-error tests initially exposed invalid synthetic retry metadata and a mismatched localized assertion. Fixed the fixture/assertion, not production validation.
- Final focused regression, architecture, grouping and resize suite: 25 tests passed. TypeScript/production build passed with existing chunk-size warning.
- Fresh full run after fixture correction: all 535 tests passed across 62 files.
- Browser synthetic fixture: pagination and disclosure work; drag 560 to 860; wide data grid has three columns; mobile override 390 (433 CSS px at browser zoom) has one column and no document overflow.
- More menu, scope text, focus after opening, Escape return to More, and browser error log checked. No captured browser errors.
- Screenshot capture recovered on the follow-up verification. Reviewed the rendered collapsed and expanded operation and the widened three-column usage layout in the synthetic browser fixture. This does not verify a live provider connection. Installed runtime remains unchanged.
