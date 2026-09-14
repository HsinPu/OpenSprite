# Native provider tool transports

## Approved scope

Add real non-streaming tool calls for OpenAI Responses, Anthropic Messages and
the built-in OpenRouter entry. Preserve streaming, legacy settings and approval
boundaries. Separate UI response delivery from API transport.

## Checkpoints

- Adapter slice: 44 focused tests passed, including three real-calculator
  round trips with mocked native JSON responses and existing streaming tests.
- Settings and immutable snapshot integration completed. Old settings retain
  streaming; native policy is stored in existing AI settings, custom policy in
  its existing provider record. No credential migration.
- Native provider live credentials are unavailable; do not claim live success.

## Verification

- Focused backend regression: 139 passed, 1 unrelated version assertion deselected.
  Covers native JSON tool round trips with the real calculator, existing streaming
  adapters, multiple calls, duplicate IDs, malformed/truncated responses, plain
  JSON text, AI settings migration, provider-only updates, immutable run policies,
  context receipts and API route contracts.
- Full backend run before the final route-contract assertion update: 1131 passed,
  3 skipped, 5 failed. The new route assertion was corrected and passed in the
  focused rerun. Four pre-existing tests still hardcode version 0.21.0; the local
  Python package metadata reports 0.21.14. No version change was made in this slice.
- Full frontend: 63 files / 541 tests passed. TypeScript and production build pass;
  existing large-chunk warning remains.
- Browser preview inspected at desktop, 768px and 390px widths. Native tool modal,
  advanced model exceptions and controls fit; Escape closes only the modal and
  restores focus to its opener. No settings were saved to the older installed
  backend. Preview tab and temporary viewport were cleaned up.
- No live native-provider API validation: OpenAI, Anthropic and built-in OpenRouter
  have no configured credentials. Mocked transport success is not live proof.
- No automatic fallback/replay was added. Existing permission and approval checks
  still apply. Invalid tool-shaped text is never promoted into a tool execution.

No commit, version bump or local deployment has been requested for this slice.
