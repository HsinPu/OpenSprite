# Windows uninstall when a child process exits during shutdown

An actual uninstall of installed build 0.21.16 / d2d241c2 stopped the backend,
then aborted because another PID from the CIM snapshot had already exited.
The startup entry had been removed, but the application directory remained.

The uninstaller now treats only Stop-Process's NoProcessFoundForGivenId error
as an already-completed stop. Other failures still abort before deleting the
application. Data removal policy and path validation are unchanged.

Verification:
- The process pipeline regression covers ordinary stops, an already-exited child,
  unrelated processes, a real stop failure and WhatIf. Windows PowerShell 5.1 passes.
- The full Windows test.ps1 suite passed, including prerequisite/bootstrap/package/
  recovery checks, a real isolated build/install, installed runtime validation,
  and uninstall. Only the existing large frontend chunk warning was reported.
- git diff --check passed.
- The corrected installed uninstaller exited 0; the official app directory and
  startup entry were removed, and port 8765 had no listener.
- Both existing user-data files remained present with identical SHA-256 hashes.
  Git, Node.js/npm and uv remained installed.
- The pre-existing locked .app-prepared directory from installation was retained;
  it is outside the application directory and is not swept by this fix.
