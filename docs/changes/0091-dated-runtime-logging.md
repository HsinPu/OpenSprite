# 0091 — Dated runtime logging

## Objective

Preserve safe backend diagnostics and tracebacks for the installed hidden
runtime without scattering file ownership across Agent, Provider or storage code.

## Changes

- Added one centralized dated runtime handler under `.opensprite/logs/backend`.
- Added 10 MiB rotation, two backups, 14-day bounded retention and secret-like
  text redaction across messages and tracebacks.
- Connected logging to the FastAPI lifespan, runtime failures, Agent context
  events and RunManager failures while keeping System Prompt receipts separate.
- Added bootstrap-only Windows launcher errors and bumped the product to 0.2.0.

## Safety

Runtime logs contain identifiers, limits, counts, status and tracebacks, but do
not intentionally contain prompts, conversation text, model output, credentials
or Provider bodies. Retention only removes resolved ISO-date directories directly
below the backend log root and never follows links.

## Verification

The backend suite passed 474 tests with 2 platform skips. The frontend suite
passed 178 tests plus TypeScript and production build checks. Compileall,
offline lock, dependency validation and Windows installer isolation also passed.
Local-install and live log evidence is recorded in the final task handoff.
