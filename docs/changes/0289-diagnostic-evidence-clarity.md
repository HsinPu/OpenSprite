# Diagnostic evidence clarity (in progress)

- Display existing compaction start receipt: trigger, history sequence range, request estimate and input budget.
- Do not mislabel summary API input/output usage as before/after context size.
- Explain run completion versus verified task success, cancelled usage and possible reasoning usage.
- Preserve structured tool-call-only execution. Live calculator requests previously returned ordinary JSON text twice; root cause is still under investigation.
- TypeScript check passed. Diagnostic presentation tests: 10 passed, including real validated start/completed compaction receipts.
- Custom-provider gateway tests: 4 passed, including new paired formal tool_calls versus ordinary JSON content cases. The request includes tools and auto tool choice; only the formal protocol produces ModelToolCall. This rules out automatic execution of JSON text but does not prove the remote provider behavior.
- Python tests required host access; pytest cache writes are blocked, so verification used -p no:cacheprovider with -W error retained.
- Live provider root cause and rendered verification remain pending; this is not a completed goal or deployed update.

## Capability mismatch found

- Read-only local catalog inspection confirmed the active custom glm-5.3-flash model has tools=false, while the recorded request advertised calculator.
- AgentLoop gated Skill/delegation tools but did not gate regular tools on supports_tools. Now the run availability is empty for such models, with an explicit model instruction explaining the limitation.
- Added a regression with an unsolicited structured call to verify disabled model tools are neither advertised nor executed. Provider configuration was not changed.
- This confirms a local capability-enforcement defect; it does not prove why the upstream model emitted textual JSON or claim that enabling tools would make that model compatible.

## Broader verification

- Agent loop, custom inference, native adapters, context runtime and receipt regressions: 89 passed with warnings treated as errors and pytest cache disabled.
- Production frontend build and TypeScript passed; existing chunk-size warning remains. git diff --check passed.
- Full frontend suite: 62 files and 536 tests passed. jsdom reports its existing pseudo-element getComputedStyle limitation; no tests failed.
- Local runtime update consent was requested before real browser verification; installed service has not been changed in this goal. Rendered and real-message verification remains pending.

## Installed runtime and first live regression

- After user approval, the Windows installer deployed the current working tree at version 0.21.14. Health returned ok and HTML served index-BsDp8VOa.js and index-BnGV7qS2.css. Old program backup cleanup emitted locked-directory warnings; the process handle was unavailable on follow-up, so a final installer exit code was not captured.
- Through the browser, submitted the synthetic DIAGNOSTICS-FIX-0913 calculator request in conversation 9a83dc27-977d-46c4-87ea-6c3ef30a7e6b. The model explicitly explained that tools are disabled, did not simulate JSON calls, and identified its arithmetic as not tool-verified.
- The actual execution panel reported no additional tools. The diagnostic drawer showed the completion qualification, provider input/output 566/716, estimate 865, budget 20,480, reserve 8,192, and the usage caveat. Desktop screenshot inspection showed readable aligned rows without visible overflow at the default 560px drawer width.
- This validates the disabled-tools live branch, not a successful enabled tool call. Compaction/cancellation and responsive live checks remain outstanding.

## Live cancellation regression

- In the same synthetic conversation, sent a request for a long software testing explanation, then clicked Stop while the request was in progress. It stopped after 8.3 seconds; input became editable again and the diagnostic model attempt showed cancelled.
- Expanded details explicitly said unreported usage does not mean no cost. Only request estimates were displayed (1,183 input estimate, 20,480 budget, 8,192 reserve), without fabricated zero actual usage.
- Keyboard resizing changed the drawer from 560px to 520px; screenshot inspection found no visible overlap in this case. Home restored 560px. This is desktop narrow-drawer evidence, not mobile viewport coverage.

## Live compaction presentation finding

- Opened the real historical 13:37:30 run in conversation 552b46ae-866c-4b1b-a9ba-7ebae6a715f6. It showed history range 3–4, estimated-before 20,104 and budget 20,480, plus the summary-usage distinction.
- The old translation incorrectly said the local input budget was exceeded. The assembler uses proactive selection trigger/target budgets, so local_budget does not prove the displayed hard input budget was exceeded. Changed all three locale labels to local context budget management and added a negative assertion against the misleading label. No compaction thresholds or runtime behavior changed.
- This additional copy correction is not yet installed; post-change browser and mobile checks remain pending.

## Responsive and copy regression verification

- Corrected-label diagnostic regression: 10 tests passed. Existing jsdom pseudo-element warnings remain.
- Inspected real historical compaction at 390x844 and 768x1024. At mobile width the dialog bounds and scroll width were both 390px; a settled screenshot showed the close control, labels and values in bounds with wrapping. Tablet screenshot also showed readable rows. Reset the viewport afterward; captured browser error log was empty.
- The final label correction is being deployed through the same authorized installer (session 5263); final rendered text verification is pending.

## Final functional verification

- Health returned ok and the installed HTML serves index-BRDlF7AS.js. Reloaded the real historical conversation and confirmed the displayed reason is now local context budget management, with unchanged range 3–4, estimate 20,104 and budget 20,480.
- Requirement evidence: formal protocol/text separation and disabled-capability enforcement are covered by backend tests; a real browser request confirmed no advertised tools and no simulated invocation; completion and cancellation semantics were inspected live; historical real compaction receipts expose reason/range/estimates without presenting summary output as post-compaction context size; desktop, mobile and tablet renderings were inspected.
- Scope limits: no claim that the remote tools-disabled model supports formal tools when enabled; no model capabilities, credentials or compaction thresholds changed. No commit, push or version bump. The installer retains locked old program backups rather than forcing their deletion; cleanup warnings are separate from the healthy serving runtime.
