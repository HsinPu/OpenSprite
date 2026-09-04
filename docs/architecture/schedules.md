# Durable Agent schedules

OpenSprite owns one in-process schedule coordinator inside the backend lifespan.
SQLite schema v12 stores schedules, Workspace ownership and occurrences;
operating-system schedulers only keep the single OpenSprite backend available
and never own individual jobs.

## Execution model

A schedule uses once, daily, or weekly cadence in an IANA time zone. Its
provider, model, reasoning mode, Context budget, output budget, and continuation
policy are snapshotted when the schedule is created or edited. The Schedule also
stores an explicit Workspace ID and never follows the Sidebar's active
Workspace. System Prompt, credentials, enabled tools and the immutable Workspace
execution context are resolved when each occurrence executes.

The first accepted Run creates a dedicated Conversation and binds it to the
schedule. Later occurrences reuse that Conversation. Deleting a schedule removes
schedule and occurrence metadata through SQLite foreign keys but does not delete
the Conversation, Messages, or Runs.

Changing a Schedule's Workspace is allowed only while it has no pending or
running occurrence and its dedicated Conversation has no active Run. The
Schedule and Conversation Workspace IDs then change in the same SQLite
transaction. A missing or inaccessible Workspace root is shown as a warning but
does not prevent a text-only scheduled Run.

One coordinator provides global schedule concurrency of one. Each occurrence ID
is also the Run client request ID, and database uniqueness constraints make
claiming restart-safe. Pending occurrences are recovered after restart. Running
occurrences are reconciled from durable Run state before new work proceeds.

## Time and missed runs

Daily and weekly local times use `zoneinfo`. A nonexistent DST time advances to
the first valid minute after the clock jump; an ambiguous time selects the first
instant only. After downtime, only the latest occurrence within 15 minutes runs.
Older times collapse into one skipped occurrence with `missedCount`. Paused time
is never backfilled, and resume computes the next future occurrence.

Scheduled Runs never enable full Prompt logging. Read-only tools may execute;
any tool that requires human approval fails the Run and occurrence with
`scheduled_tool_approval_required`. The scheduler cannot create or accept an
approval.

## Host continuity

Windows continuity is login-only: shutdown, sleep, or a signed-out user cannot
run schedules. Linux user services may continue after logout only when user
lingering is enabled. The installer detects and warns but never invokes `sudo`
or changes linger policy.

Schedule management lives under Settings rather than the primary conversation
navigation. The UI polls the authenticated schedule API every five seconds only
while Settings is open on the Schedules section. Create and edit forms always
send a Workspace ID, defaulting to the current Workspace. Schedule cards and
selector options show an unavailable or missing Workspace warning without
disabling text-only execution. A Workspace catalog load failure has its own
retry action and temporarily disables Schedule create/edit instead of showing a
permanent loading label. There is no WebSocket, OS notification, Email, or push
notification in version 0.11.0.
