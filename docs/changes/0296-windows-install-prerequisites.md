# Windows installer prerequisite setup

Local source installation now reuses the standalone download installer's winget
preflight. Missing Node.js/npm and uv prompt for consent; InstallPrerequisites
supplies explicit consent and NonInteractive rejects missing tools without it.
InstallGit optionally includes Git.Git, without requiring Git for source/ZIP
installation. Existing unsupported Node versions still require manual upgrades.
Missing npm offers the Node.js LTS package and tools are rechecked after PATH refresh.

Bootstrap remains standalone and is included in both release archives and staged
installations. Local WhatIf returns before prerequisite installation. The default
SourceRoot is resolved in the script body to support the documented Windows
PowerShell entry without explicit SourceRoot.

Verification:
- Prerequisite isolation tests pass: required/optional package selection, exact
  winget arguments, PATH recheck, failed install, noninteractive consent guard,
  and the documented entry with WhatIf and omitted SourceRoot.
- Existing bootstrap, release packaging and recovery isolation tests pass.
- git diff --check passes.
- winget is mocked; no real system package installation was performed. Full
  application build/start remains unverified here because npm/uv are unavailable.
- No installed application or OpenSprite user data was changed.
