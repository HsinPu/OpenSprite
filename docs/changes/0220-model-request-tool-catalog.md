# Complete model-request tool catalog validation

Remove the remaining 64-tool cap in ModelRequest, completing the 0.19.3
tool-catalog correction. Message bounds, duplicate-tool checks, Context budgets
and execution limits remain unchanged.

Add a real AgentLoop/SQLite integration with a deterministic gateway: 64, 65 and
131 total definitions, including both internal Skills tools. Load a Skill,
invoke a regular tool, then finish; assert all three requests and model.started
events retain the complete catalog. Before the fix, 64 passed while 65/131 failed
with invalid request bounds. After the fix, all 50 Agent/Skills tests passed,
including the three new cases. All 37 inference adapter tests, compileall,
offline lock/dependency checks and git diff --check passed. The full suite was
not rerun for this one-line follow-up.

No version bump, commit, push or installed-runtime update. The gateway is a test
double; this does not establish a real provider's tool-count capabilities.
