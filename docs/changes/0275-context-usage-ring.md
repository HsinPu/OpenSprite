# Context usage ring

- Replace the composer text badge with an 18px Ant Design progress ring inside a 40px keyboard-accessible button.
- Show context usage and the effective context limit in a popover; preserve unknown usage rather than presenting it as zero. Cap the ring at 100% while retaining the actual percentage in text.
- Support hover, focus, click and Escape. Keep existing theme colors and label the value as the latest request estimate in Traditional Chinese, English and Japanese.
- Do not change backend limits or compaction behavior.

## Verification

- TypeScript and Vite production build passed (existing chunk-size warning).
- Focused indicator tests passed before browser review; browser review caught focus/click double-toggle and the implementation was corrected.
- Desktop isolated component preview verified unknown, 0%, 25%, 76%, 100% and 105% ring rendering and visible 76% popover.
- Indicator and ChatWorkspace integration tests: 37 passed, including hover/focus/blur, click/Escape and invalid limits. jsdom emits its existing pseudo-element getComputedStyle warning.
- 375px viewport isolated component review verified the popover fits without clipping; actual Tab focus and Escape dismissal verified. Full installed-app visual testing was not performed because the local login service was unavailable; no installed runtime was changed.
- `frontend/context-usage-preview.html` is a manual Vite-only entry, not part of the production build; it uses synthetic data and does not call providers.
- No commit, version bump or installed-runtime deployment performed.
