# Skill folder import review remediation

Version remains 0.14.0. Resolve the three findings from the folder-import review
without changing file payload quotas or executing supporting files.

1. Metadata quota: allow a bounded 1 MiB manifest, sufficient for 200 portable
   paths and JSON Unicode escaping. Bound the whole request to 10 MiB payload,
   1 MiB manifest and 64 KiB framing. Regression coverage submits 200 files with
   seven-level paths and a manifest larger than the former 64 KiB cap; an
   oversized manifest is still rejected.
2. UTF-8 BOM: ignore only a leading signature while parsing SKILL.md. Preserve
   original disk bytes and SHA-256 so preview, import, later reads and explicit
   enablement agree. An API test imports BOM content, verifies byte/hash
   preservation and then explicitly enables the imported version.
3. Duplicate manifest keys: translate the JSON duplicate-key exception at the
   request boundary into non-retryable 400 invalid_request. Do not misreport
   malformed input as a persisted-catalog 503 failure.

Verification: complete backend pytest with warnings as errors passed (786
passed, 3 skipped); compileall, offline uv lock check and uv pip check passed.
Frontend implementation is unchanged; focused folder-import/settings regression
tests were rerun. No installer/browser deployment or Linux GUI verification was
performed for this remediation. No commit, push or local installation update.
