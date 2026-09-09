# Release 0.19.1

Patch release for the recovery boundary fixes recorded in 0213:

- Preserve the original request when submission outcome is uncertain.
- Retry terminal hydration failures with a bounded recovery policy.
- Adapt Skill discovery page size to remaining Context budget.

Update authoritative package metadata, lock metadata, README, the Skills
contract version and version assertions. Historical change records retain
their original versions. Frontend package and Node engine versions are unchanged.

Verification: 35 build-info/app-info/app contract tests passed; offline lock
check, dependency compatibility and git diff --check passed.
No local installation, commit or push is performed.
