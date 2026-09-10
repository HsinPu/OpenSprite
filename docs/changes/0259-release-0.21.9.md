# Release 0.21.9

## Scope

- Bump the authoritative backend package version and lockfile from 0.21.8 to 0.21.9.
- Update the README release summary for the General settings layout delivered in change 0258.
- No dependency, backend behavior, or preference default changes.

## Included changes

- Group General settings into language and time, conversation preferences, and execution panel settings.
- Use Ant Design selects, collapse planned features by default, and clarify scoped reload errors.
- Preserve existing persistence behavior and colors while improving Traditional Chinese, English, Japanese, and narrow layouts.

## Verification

- Change 0258 records 451 passing frontend tests, typecheck, build, and browser checks at four viewport widths.
- Release metadata verification: `uv lock --check --offline` and `git diff --check`.
- This slice only updates repository version metadata; it does not install locally, commit, or push.
