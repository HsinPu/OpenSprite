# Windows runtime shutdown failure

- Propagate process termination failures and wait up to ten seconds for exit before continuing installation.
- Abort application and access-state rollback when shutdown cannot be confirmed, retaining backups and reporting the manual recovery requirement.
- Add an isolated mocked termination-error regression and a rollback guard check; no real service is stopped by these tests.
- No version bump or local deployment. Live service failure injection remains unverified.
