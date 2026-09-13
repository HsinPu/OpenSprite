# Frontend agent rule coverage

- Compared the user-supplied 85-rule frontend standard with the existing root
  AGENTS.md. Its requirements were already consolidated into 12 sections.
- Explicitly identified that section as canonical frontend guidance and added
  a mapping from all 85 original rules to the maintained sections.
- Preserved repository, user-data, verification, theme and branding boundaries.
  No duplicate rule set, frontend code change, deployment or version bump.
- Verification: reviewed coverage for rules 1–85 and ran scoped git diff --check.
