# Windows release bootstrap

## Changes

- Add a stable-release GitHub downloader with explicit version resolution,
  HTTPS redirect allowlist, size/time limits, SHA-256 checks, safe extraction and
  owned-temp cleanup. No Git requirement on the target machine.
- Missing prerequisites require interactive or explicit consent to winget;
  noninteractive missing-tool calls fail closed. Existing old tools are not replaced.
- Share an installation mutex with the existing installer, preserve source
  revision from release metadata, use frozen Python dependencies, and prepare
  dependencies before cutting over. Preserve user data/access settings.
- Retry recognized retired application backups only after healthy startup;
  locked files remain with warnings. Do not sweep failed-install recovery trees.
- Add allowlisted source packaging and a manually dispatched, draft-only GitHub
  Release workflow. No release, tag, version bump, commit, push or local deployment
  was performed by this implementation.
- Shorten isolated test-root names for PowerShell 5.1 path limits, and include
  preparation environments in the existing test-only native-file quarantine.

## Verification

- Windows PowerShell 5.1 parser, bootstrap safety/orchestration tests, packaging
  fixtures and existing recovery tests passed.
- Workflow YAML parsed successfully; hosted execution has not been performed.
  Final diff whitespace checks passed.
- Tests exercise checksum mismatch, unsafe ZIP paths, links/corrupt archives,
  prerequisite refusal/unavailable winget, fixed-version mismatch, successful
  delegated install and success/failure cleanup. Package tests verify allowlisted
  output, provenance and rejection of dirty checkouts.
- Full installer isolation verification passed, including actual frontend build,
  Python dependency preparation/final installation, metadata checks and uninstall.
  Locked test-native binaries were quarantined and retained with warnings.
- Actual GitHub release download, hosted workflow execution, winget installation,
  and clean-Windows first-install smoke testing require a published test release
  or disposable Windows environment; they are not claimed here.
- Initial full runs exposed long test paths and Windows native-file locks;
  subsequent test cleanup handles both without deleting user data.

## Remaining release gate

Publish only after reviewing the draft artifacts and a clean-Windows smoke run.
Checksum files come from the same GitHub trust boundary, not an independent signature.
