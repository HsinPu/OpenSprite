# Move schedules into Settings

## Objective

Keep conversation navigation focused on chat and manage durable schedules from
the existing Settings surface.

## Changes

- Removed the main-sidebar schedule action, independent `#schedules` view state,
  and chat-workspace replacement.
- Added an implemented Schedules category after Tools in Settings with a native
  calendar icon and complete Traditional Chinese, English, and Japanese copy.
- Reworked the schedule view for the Settings content width and its single
  scroll owner.
- Schedule polling now runs only while Settings is open on that category.
- Nested Ant Design dialogs, drawers, selects, and confirmations render inside
  the native Settings dialog.
- The long desktop schedule form scrolls inside its Modal instead of expanding
  the Settings dialog or browser page.
- Opening a dedicated schedule conversation closes Settings, keeps the mobile
  sidebar closed, updates the chat hash, and restores focus to the main area.

## Compatibility

The schedule HTTP API, SQLite v11 data, coordinator, and stored schedules are
unchanged. The removed `#schedules` hash follows the existing unknown-hash
startup behavior instead of becoming a second compatibility route.

## Verification

Frontend tests cover Settings placement, absent sidebar navigation, removed hash
normalization, polling lifetime, nested overlay placement, responsive editor,
localization, and scheduled-conversation navigation.
