# 0202 — Skill ZIP import (0.15.0)

- Replace browser directory selection and the folder-upload endpoint with
  a single ZIP upload. Preserve individual SKILL.md import and existing Skills.
- Ant preview remains local until confirmation, shows target scope, editable
  directory name, metadata, file list, expanded size and entrypoint content.
- Accept one optional wrapper directory. Backend independently validates
  archive types, CRC, paths, duplicate names, links and resource bounds.
- Limits: ZIP 12 MiB, expanded total 10 MiB, 200 files, depth 8,
  SKILL.md 64 KiB and other files 5 MiB. No script execution or auto-enable.
- Reuse the recoverable package transaction, revision checks and archive policy.
- Browser uses pinned fflate 0.8.3 with actual streaming-output bounds;
  backend uses Python zipfile in memory without extractall.
- Keep required name/description and optional safe YAML metadata; description
  has no separate character cap. Update version, README and HTTP contract.

Verification:

- Backend: 807 passed, 3 skipped (`pytest -p no:cacheprovider -W error`).
  The cache plugin is disabled because an existing cache directory has a
  Windows ownership restriction; warning checks remain enabled.
- Frontend: 322 passed; typecheck and production build passed.
- compileall, uv lock --check --offline and uv pip check passed.
- Windows installer isolation passed; its native-binary quarantine warnings
  remain visible. Linux Bash syntax checks passed.
- git diff --check passed; SymbolLattice 0.513.0 reports a fresh index,
  matching the current checkout guidance.
- Browser automation/real Linux GUI/systemd were not exercised in this slice.
  The installed application was not updated, and no commit or push was made.
