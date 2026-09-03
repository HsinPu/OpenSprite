# Schedule management page

## Objective

Add the authenticated browser workflow for creating, monitoring, and managing
durable Agent schedules on desktop and mobile.

## Changes

- Added `#schedules` navigation below New Conversation without changing chat URL
  restoration.
- Added strict frontend API validation, five-second page polling, grouped Active,
  Paused, and Completed cards, latest status, and paged occurrence history.
- Added create/edit, pause/resume, run-now, delete confirmation, and dedicated
  conversation actions.
- The editor supports once, daily, and weekly cadence, IANA time zone, weekdays,
  and the complete fixed execution profile.
- Desktop uses an Ant Design Modal; viewports at 767px and below use a full-width
  right Drawer with touch-sized controls and focus restoration.
- Added complete Traditional Chinese, English, and Japanese strings.

## Verification

- Frontend API tests cover exact request paths, strict success parsing, and safe
  error parsing.
- Component tests cover grouped actions, occurrence history, desktop Modal, and
  390px Drawer behavior.
- App navigation, locale parity, TypeScript, and existing frontend tests remain
  covered by the broader frontend suite.
