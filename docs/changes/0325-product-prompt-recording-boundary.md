# Product Prompt and optional recording boundary

- Product version: `0.21.40` -> `0.21.41`.
- Scope: separate product rendering from optional complete Prompt receipts;
  preserve Host API v5 and mandatory execution persistence.

The renderer now returns a frozen product snapshot without filesystem effects.
The admitted `logFullPrompts` setting controls both System Prompt and complete
request receipts. An explicitly composed product recorder writes through a
bounded lazy daemon worker, with at most four pending records and an 8 MiB
content ceiling per record. A full queue or unavailable filesystem only emits
a sanitized diagnostic. Shutdown drains for at most two seconds.

Host request notifications replace direct filesystem writer dependencies. They
do not change inference inputs, source receipts, request counts or transactions.
The System Prompt template and required v5 prefix remain unchanged. The three
interface locales and the existing AI settings contract describe the policy.

Validation: the focused rendering, policy/fault, Agent loop, dependency, SDK v5
and runtime suite passed **67 tests**, with **1 POSIX-only permission test skipped
on Windows**. SettingsPage and i18n frontend checks passed **40 tests**;
TypeScript, compileall, dependency consistency and `uv lock --check --offline`
passed. Native restricted pytest first
encountered Windows cache/temp ACL errors; the scoped unsandboxed run used a
fresh repository temporary directory and disabled the optional pytest cache.
Cross-platform receipts, complete frontend checks and live Docker/browser checks
are deferred to the final integration stage. Isolation of product preparation
and product packaging is the next independently versioned stage.
