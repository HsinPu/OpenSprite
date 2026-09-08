# 0203 — Complete ZIP directory validation

Address review findings P2 (preview skips empty-directory validation) and P3
(backend skips forbidden wrapper/empty directories). Validate all archive nodes
before stripping wrappers or ignoring empty directories, including portable
names, forbidden directories, case collisions and file/directory conflicts.
Keep valid explicit directory records before or after child files compatible.

Version remains 0.15.0. No installed-data changes, commit or push.

Verification: focused backend package/ZIP tests 62 passed; frontend package,
ZIP and settings tests 40 passed. Typecheck, production build and diff check
passed; SymbolLattice reports a fresh index. Full suites and real-browser
interaction were not repeated for this bounded correction.
