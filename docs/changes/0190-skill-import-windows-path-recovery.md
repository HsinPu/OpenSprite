# Windows Skill folder paths and failed import isolation

Remediate the confirmed P1: an accepted long-path package failed while creating
its stage on Windows, leaving a journal that blocked every subsequent Skills
catalog read. Version remains 0.14.0.

Package disk operations now use Windows extended-length paths for the derived
target and stage. Catalog paths and uploaded relative paths do not change.
Existing directory/reparse checks remain in place. This does not change the
Windows registry or require enabling system-wide long-path policy.

For a caught write failure before target publication, preserve the stage as
`archive/skills/failed-import-<skill-id>-<attempt-id>/payload` and move its
journal to the sibling `transaction.json`. The catalog is unchanged and the
next request can read existing Skills or explicitly retry. Uploaded files named
transaction.json cannot collide with the archived transaction record.

Do not discard evidence when the target already exists, the archive cannot be
written, or the catalog cannot be committed. Published targets still use the
existing verified roll-forward path; mismatches remain fail-closed.

Verification includes real Windows disk creation for 200 files with seven-level
paths exceeding 260 characters, readback, archive deletion, and recreation of
the service after an interrupted catalog commit. Injected stage-write failure
preserves the prior Skill, archives partial bytes, and allows an explicit retry.
Focused package tests: 38 passed. Compileall, offline uv lock and uv pip check
passed. Full backend pytest with warnings as errors: 788 passed, 3 skipped.
Git diff check passed and SymbolLattice 0.511.0 reported a fresh index.

No frontend behavior changed. No install, push or commit was performed.
Real Linux GUI/systemd and browser deployment were not rerun for this fix.
