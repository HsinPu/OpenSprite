# Unified custom-provider tool policy

## Scope and phases

1. Provider-wide tools_enabled gate, new-provider compatibility defaults, preserved legacy opt-outs and immutable execution snapshots.
2. Provider form owns defaults; model tools=true means inherit, tools=false is the existing individual opt-out. Advanced model selector exposes these two choices. Discovery and manual creation default to inherit.
3. Context receipts record policy source and API transport alongside advertised tool count. Old receipts remain readable with unreported values. Formal tool calls only; permissions and approvals unchanged.
4. Update local runtime, explicitly enable LiteLLM policy/compatibility and set its existing models to inherit via UI; test synthetic calculator conversations.

## Data and compatibility

- No destructive migration, credential changes or speculative capability claims.
- Catalog records missing tools_enabled read as true; missing non_streaming_tools remains false to preserve old installations.
- New provider API/service/UI defaults both controls to true. Omitted settings on updates preserve previous choices.
- Existing model tools fields are reused, not duplicated. True is an opt-in to provider inheritance, not verified vendor capability. Existing false values remain individual opt-outs unless explicitly changed.
- Both live capability resolver and run snapshot use CustomProvider.allows_model_tools.
- Refresh preserves existing model metadata; no global permission widening.

## Verification

- Phase 1: 26 focused backend tests passed with warnings treated as errors.
- Phase 2 frontend typecheck/build passed. Full frontend run: 62 files, 539 tests passed (before the final additional API decoder assertion).
- Phase 3 final focused backend run: 33 passed with warnings treated as errors; compileall passed. Real CalculatorTool is invoked in both mocked transport round trips.
- Full backend run: 1119 passed, 3 skipped, 5 failed. One new request-hash/log mismatch was corrected and its regression passed. Four remaining failures are pre-existing 0.21.0 version assertions vs current package/repository versions; version metadata was not changed in this slice.
- HTTP model edits that omit tools preserve the existing opt-out under the mutation gate.
- Final API decoder test file: 7 passed; git diff --check passed.
- Local installer exited 0; runtime 0.21.15 / 23e5a7f0 dirty build started successfully. Locked previous/prepared installation directories remain (cleanup incomplete); no user data or credentials were deleted.
- Browser verified LiteLLM tools enabled and non-streaming compatibility enabled after reopening the form. All three existing models displayed inheritance; no capacity/default-model changes were made.
- Real browser conversation 9fe8579c-209d-4bc5-ae28-ff0b043a1d9e: calculator 7391*4827 returned 35676357 with an actual tool execution event. Diagnostics showed inherited provider policy, non-streaming transport and 3 advertised tools.
- Chained browser request produced two distinct tool-start/tool-complete pairs (3973 then 4056), followed by a final reply. A no-tools ordinary reply returned the requested text with no tool execution.
- Real provider validation covers LiteLLM/glm-5.3-flash in compatibility mode, not all models or native streaming at that endpoint. Both transport paths are covered by mocked integration tests using the real calculator implementation.
- Desktop model list and provider form visually inspected. Tablet/mobile viewport checks were attempted and reset; the in-app viewport capture showed right-edge clipping, so full responsive clearance is not claimed and needs a separate layout investigation.
- No commit or version bump requested for this slice.
