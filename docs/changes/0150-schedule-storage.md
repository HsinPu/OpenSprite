# Durable schedule storage

## Objective

Add the durable schedule and occurrence model plus timezone-safe recurrence
calculation without starting background execution yet.

## Changes

- Added once, daily, and weekly schedule domain records with fixed execution
  profiles and IANA timezone recurrence.
- Added SQLite v11 schedules, occurrences, Run source/occurrence metadata,
  uniqueness constraints, indexes, cursor pagination, and revision conflicts.
- Added DST handling that advances nonexistent local times to the first valid
  minute and selects the first instant for repeated local times.
- Added pinned `tzdata` so IANA zones work consistently on Windows.

## Public impact

Existing v10 conversation databases migrate in place without changing current
chat behavior. No schedule HTTP or UI surface is exposed by this slice.

## Verification

- Schedule CRUD, pagination, occurrence uniqueness, revision conflict, and DST
  tests.
- Conversation migration regression tests from historical schemas through v11.

## Remaining work

Coordinator execution, HTTP API, tool policy, frontend UI, and runtime lifecycle
are delivered separately.
