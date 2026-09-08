# Skill header compatibility

- Require nonempty string name and description while accepting additional safe YAML metadata fields.
- Remove the description character limit in parsing, persisted catalog validation, browser preview and response validation.
- Keep the 64 KiB document size limit, duplicate-key rejection, safe YAML parsing, and nonempty body requirements.
- Additional metadata is preserved in the document and does not grant tool permissions.
