# Windows bootstrap in restricted PowerShell sessions

The published one-command source installer downloaded and cloned successfully,
then failed to invoke `install.ps1` in Windows PowerShell 5.1 with the default
`Restricted` execution policy. The in-memory bootstrap itself could run, but
its file-backed installer and dot-sourced helpers could not. Existing checks
ran under `Bypass` and did not cover that caller environment.

The bootstrap now saves the process execution-policy environment value, sets
`Bypass` at `Process` scope immediately around installer invocation, and restores
the original value in `finally`. This includes restoring an absent value, and
works when installation throws. No `CurrentUser` or `LocalMachine` setting is
written. The standard PowerShell cmdlet preserves Group Policy precedence.
The same invocation path serves source and release installations, and remains
in the existing process/thread so the reentrant installation mutex still works.

Bootstrap regression checks now load the entry point in memory and run the
orchestration tests in Windows PowerShell child processes with `Restricted`,
`AllSigned`, and an unset process policy. The fixture installer also dot-sources
a helper. Tests cover both download modes, installer failure propagation,
temporary cleanup, failure-stage reports, and exact restoration of the process
environment value and all execution-policy scopes. Downloads and prerequisites
are local fixtures for these policy regressions; they do not alter the real
application or user data.

Verification:

- Before the fix, the new `Restricted` process check reproduced the reported
  `UnauthorizedAccess` failure when invoking the downloaded installer.
- After the fix, bootstrap checks passed in Windows PowerShell 5.1 under
  `Bypass`, `Restricted`, `AllSigned`, and inherited policy with no process
  environment value. Successful source/release calls and injected installer
  failures left the original policies unchanged.
- The full Windows `test.ps1` suite passed: prerequisite, bootstrap, packaging,
  recovery and uninstall regressions, plus an actual isolated build/install,
  installed Python runtime check and uninstall. The existing large frontend
  chunk warning was reported.
- `git diff --check` passed. The policy checks write no persistent policy and
  leave the user's real installation and product data untouched.

Microsoft documents the process-scoped environment value and Group Policy
precedence in its [Windows PowerShell execution-policy reference](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/main/reference/5.1/Microsoft.PowerShell.Security/Set-ExecutionPolicy.md).
