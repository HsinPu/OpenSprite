# Skill folder selection and confirmation

Keep single Markdown import and add Ant Design folder selection. Before network
submission, validate relative paths, file count/size, entrypoint and safe YAML
front matter using pinned yaml 2.9.0. Preview display name, physical directory,
description, all relative paths/sizes and read-only SKILL.md contents.

The explicit confirmation uploads the package; selecting/cancelling never saves
or enables it. Reuse desktop Modal/mobile Drawer, busy guards and Escape/focus
handling. All new interface copy is available in Traditional Chinese, English
and Japanese. Warn that supporting files are stored only and empty directories
are not imported. Existing single-file flow remains independent.

Focused component/validation tests: 22 passed; typecheck passed. Full regression
and browser verification are recorded separately in the release slice.
