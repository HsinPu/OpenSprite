# Windows installer preflight and recovery

- Resolve and exercise Node, npm and uv before staging or cutover; reject unsupported Node versions.
- Forward custom-install authorization during first launch and rollback launch.
- Isolate failed application directories instead of requiring recursive deletion before rollback.
- Recovery steps report individual failures and continue restoring access state. Restore access state before restarting the old application; do not restart when application/state recovery failed.
- Preserve failed application/backup directories when Windows refuses rename; report their locations for manual recovery. This cannot override OS file locks.
- Add function-level isolated recovery tests, missing-tool checks and launch forwarding assertions; include them in the existing installer suite.
- No product version bump or changes to the real installation.
- Verification: installer isolation suite passed; recovery functions tested in PowerShell 7 and Windows PowerShell 5.1, including a blocked rename followed by recovery after releasing the handle. Full live rollback/startup fault injection remains unverified. Isolation cleanup still reports Windows-held native binaries.
