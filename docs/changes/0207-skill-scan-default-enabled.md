# Enable valid newly scanned Skills

- Newly discovered valid Skills are enabled on explicit rescan in either scope.
- Existing registrations retain their switches. Invalid new files remain disabled;
  unsafe paths are still rejected. The master switch and workspace precedence remain authoritative.
- README and architecture guidance updated. No version bump or installed-data changes.
- Verification: 35 Skills policy/API regression tests passed; compileall and git diff --check passed.
