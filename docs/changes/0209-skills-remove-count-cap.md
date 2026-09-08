# Remove fixed Skill count limits

Removes the per-scope 100-Skill cap from scan, creation, ZIP/package import and
persisted catalog validation. Batch response parsing and archive recovery no longer
cap operations at 100 entries. Existing catalogs need no migration.

The existing single-file, package and JSON byte-size safety limits, duplicate-name
checks, path policy, revision checks and per-Run load budget remain unchanged.
No fixed count limit is not a promise of unlimited memory or storage capacity.

Regression coverage scans 297 files in both global and workspace scope, reloads
the catalog, adds another Skill and enables/disables/archives all 298 entries.
Frontend validates responses with counts above 100. No live user data is changed,
and the installed application is not updated by this source change.
