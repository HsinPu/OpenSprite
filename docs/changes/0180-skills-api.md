# Skills management API

Added authenticated Skills management routes with duplicate/unknown-field rejection,
revision checks, content-hash approval, explicit scanning and archive deletion.
The production runtime exposes one Skills service; unavailable runtimes fail closed.

Verification: `pytest tests/test_skills.py tests/test_skill_routes.py -W error`
passed 12 tests. Agent and frontend integration remain separate implementation slices.
