# Product version required for every commit

The repository instructions now require a product-version increase in every
commit, including documentation, tests, installers and maintenance changes.
The default is a patch increment unless the user specifies another version.

At the user's request, the complete `AGENTS.md` is also translated into
Traditional Chinese. Existing requirements, technical references, executable
examples, the 13 frontend sections and the original 85-rule mapping are retained.

The policy names `backend/pyproject.toml` as authoritative and requires the
matching backend lock entry, README current-version statement and the slice's
old/new version record to accompany the same commit. Historical change records
keep their original version references. Version consistency and an offline
lock check are required before committing.

This change applies the new rule by increasing the product version from
`0.21.16` to `0.21.17` in the same commit. The backend package, matching uv lock
entry and README current-version statement are synchronized. Dependency
versions and runtime behavior are unchanged.

Verification: inspected the existing version metadata, compared all six fenced
code examples and inline technical references against the pre-translation file,
confirmed heading/list counts and all 19 original-rule mappings are unchanged,
verified package/lock/README version consistency, and ran
`uv lock --check --offline` and `git diff --check`.
