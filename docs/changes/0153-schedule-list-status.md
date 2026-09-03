# Schedule list latest status

## Objective

Expose the latest occurrence on each schedule list item without making the
browser issue one history request per schedule every five seconds.

## Changes

- Added one bounded SQLite window query for the latest occurrence of up to 100
  schedule IDs.
- Added nullable `latestOccurrence` to schedule API responses.
- Kept full occurrence pagination on the existing history endpoint.

## Verification

- Repository coverage proves schedules without occurrences are omitted and the
  newest occurrence is selected.
- HTTP coverage proves a manual occurrence appears in the next list refresh.
