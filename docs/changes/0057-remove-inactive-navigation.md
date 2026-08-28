# 0057 Remove inactive navigation chrome

## Objective

Remove two non-functional interface groups that duplicated status or advertised
workflows that are not available.

## Changes

- Removed the chat-header Local Agent status pill and disabled overflow button.
- Removed the disabled Tools and connections shortcut from the main sidebar.
- Removed the now-unused responsive styles and three-locale message keys.
- Added regressions proving neither inactive control is rendered.

## Public impact

No HTTP contract, persisted setting, Agent Run, Provider, model-selection, or
execution-panel behavior changed. Settings remains the only sidebar utility.

## Verification

- Focused App and ChatWorkspace component tests.
- Complete frontend test suite, TypeScript typecheck, and production build.
- Desktop browser inspection for removed controls and clean header/sidebar
  spacing.
