# Custom model tool-calling default

## Scope

- New custom model forms default to supporting tool calls, including reopening after cancellation.
- Newly discovered custom models and API model requests omitting `tools` default to true.
- Existing saved models retain their explicit value; no catalog migration or live setting changes.
- Tool permissions and formal tool-call validation are unchanged. This default does not prove provider support.

## Verification

- Focused frontend tests cover checked defaults, manual opt-out, form reset, and existing disabled models.
- Backend tests cover discovery defaults and explicit API opt-out.
- Results: frontend focused suite 4 passed; backend service/routes/capability suites 16 passed; TypeScript passed.
- Backend emitted a pytest cache permission warning; tests completed successfully.
- Installed runtime and saved model settings were not modified; browser verification of the updated build remains pending.
- Production frontend build passed. Release version: 0.21.15; pyproject and lockfile updated together.
