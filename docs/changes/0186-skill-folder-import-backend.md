# Skill folder import boundary

Add package structure/name/quota validation and authenticated multipart import.
Only manifest-mapped relative paths are accepted. Content remains disabled and
supporting files are never executed. Enforce 200 files, 10 MiB payload, 5 MiB
supporting-file limit, 64 KiB entrypoint, eight path segments and portable names.

Durable journal v2 stages and verifies ordinary files before directory rename
and catalog replacement. Retain v1 support and preserve whole-folder archive
behavior. Retries use catalog revision and cannot create duplicate registrations.

Focused backend verification: 43 tests passed across folder import, Skills
policy and Skills routes. Includes interrupted catalog replacement recovery,
existing-directory preservation, global/workspace storage, archive and strict
multipart mappings. Full regression results are recorded in the release slice.
