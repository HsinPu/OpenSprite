# Sidebar user menu

- Replace separate bottom settings/logout actions with an Ant Design upward-opening user menu.
- Route Settings and About to the existing settings dialog; show logout only in password mode.
- Preserve sidebar collapse, mobile navigation close and settings opener focus behavior.
- Add Traditional Chinese, English and Japanese user labels. No account model, backend or color changes.
- Verification: UserMenu component tests (2 passed), TypeScript check and production build. Desktop/mobile visual verification remains pending; the installed runtime was not updated.
