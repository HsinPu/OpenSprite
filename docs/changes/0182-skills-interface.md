# Skills management and composer selection

Settings now provides global and Workspace Skills, explicit version confirmation,
Markdown import/editing, safe rescan, archive deletion, master switch and global
Workspace overrides. Save never silently enables new content. Failed mutations
preserve the visible state and expose a retryable error.

The composer fetches effective Skills on opening the selector, supports up to
five selections, and resets selection on accepted submission or Workspace change.
Run details display actual loaded events and distinguish manual/model selection.
Traditional Chinese, English and Japanese include lifecycle and failure states.
Small screens use a full-width Drawer and an explicit composer grid row.

Verification: 283 frontend tests passed; TypeScript and production build passed
before the final translated state-label additions (rechecked in release gate).
Tests cover explicit content-hash approval and revision-conflict preservation.
Live 390px/desktop browser interactions are not claimed by jsdom tests.
