# Skills compact list — 0.16.1

- Display Skill names in compact rows, with a right-aligned switch and icon-only remove action.
- Hide descriptions and normal-state badges from the list only; preserve descriptions in the model metadata and import preview.
- Keep exceptional-state badges, accessible action names, long-name truncation, and archive confirmation.
- Update product version to 0.16.1. No API or persistence changes.

Verification: 14 SkillsSettings component tests and 35 backend version/app contract tests passed. Frontend typecheck, production build, uv lock --check --offline, and git diff --check passed. Browser visual verification is not claimed. Installed runtime is not updated by this slice.
