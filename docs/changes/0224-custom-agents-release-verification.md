# Custom Agents release verification (0.20.0)

- Added global/workspace TOML Agent management and same-name local precedence.
- Added bounded, one-level child execution using the existing Agent loop,
  isolated Context, fixed Workspace/Skills inputs, and no approval escalation.
- Added child inspection/result pagination/cancellation routes and execution UI.
- Updated product metadata to 0.20.0. No installed-runtime update or push.

## Evidence collected

- Initial full backend run: 975 passed, 3 skipped, 1 failed. The failure was an
  unclosed SQLite connection in the new migration test, subsequently fixed.
- Focused warning-as-error rerun covering migration, contract, parent-child and
  child storage: 42 passed.
- Real configured-provider probe `scripts/verify_agents_live.py`: explicit
  delegation and discovery each completed one child, with role marker observed;
  unrelated arithmetic completed with zero children. All three cases passed.
- Controlled complete parent/child execution and parent cancellation tests pass.
- Final full backend warning-as-error rerun: 993 passed, 3 skipped. The additional
  terminal-child-start regression was run separately with the child context suite
  (3 passed) after full-suite collection.
- Full frontend suite after the mobile fix: 393 passed; typecheck and production
  build passed (existing large-chunk warning remains).
- Compileall, offline lock check and dependency compatibility check passed.
- Windows installer isolation passed, with quarantined native-binary cleanup
  warnings; the user's installed runtime was not updated.
- Git Bash syntax checks passed for Linux install/uninstall/test scripts. Linux
  helper unit tests are included in pytest; real Linux GUI/systemd is unverified.
- SymbolLattice reported initialized and fresh. Installed CLI 0.520.0 differs
  from repository guidance 0.513.0; no global installation was changed.

- Browser fixture verification: global/workspace precedence, lazy child results
  and cancellation work. The editor overflow was fixed; at 390 CSS pixels the
  Drawer spans 0..390 and its form 24..366, and a complete creation succeeds with
  focus restored to the creation button. No JavaScript errors were observed.
- Independent lifecycle review identified cancel/release, observer persistence
  failure and create/spawn races. Corrections now compensate rejected admission,
  retain safe failure codes, drain watchers and release memory without holding
  the acceptance lock during child waits. Focused regressions pass.
- The child pool now preserves cancellation/deadline outcomes even when a
  callback returns during cancellation cleanup; 11 pool tests pass.

Implementation and scoped verification are complete. Git diff check passes
under the repository's normal line-ending configuration; the index is fresh.
No push or installed-runtime update was performed. All changes remain in the
working tree for review and commit alongside the preserved pre-existing changes.

## Requirement evidence map

- Definition format, safe paths and catalog persistence: `test_agent_definition`,
  `test_agent_catalog_store`, `test_custom_agents_service`.
- NFC/current-name precedence, no fallback, independent switches and immutable
  snapshots: `test_agent_policy`; workspace cleanup and journal recovery are
  covered by service integration tests.
- Strict/authenticated management and child inspection contracts:
  `test_custom_agent_routes`, `test_custom_agents_integration`,
  `test_subagent_routes`, and app operation matrix tests.
- Durable child records, migration rollback, ownership and replay:
  `test_child_schema` and `test_child_repository`.
- Bounded concurrency, cancellation/deadline, isolated Context and tool authority:
  `test_child_tasks`, `test_child_context`, `test_child_executor`,
  `test_delegation`, `test_parent_child_execution`.
- Management/inspection UI, strict adapters and localization: frontend
  `AgentsSettings`, `SubagentExecution`, `customAgents`, `subagents`, settings
  and i18n tests; deterministic browser fixture exercises the actual components.
- Real-model routing has three controlled probe cases only; it is not a general
  delegation-quality benchmark. Cancellation remains cooperative within Python;
  no claim is made that arbitrary blocking third-party code can be forcibly killed.
