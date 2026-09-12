# Safe normalized-input receipts

- Each new attempt start records a hash of its actual normalized gateway input,
  including tool schemas and model/output settings (not provider wire encoding).
- Metadata includes selected persisted message IDs, summary ID/version/source
  hash, loaded Skill revision/hash, and workspace revision/mount-manifest hash.
- Component estimates sum to the same conservative counter used by preflight.
  System/Skills are counted once; tool definitions and framing are separate.
- Unsupported provenance remains unattributed and absent budgets remain null.
- Summary input is a single composed input category; it is not double-counted
  as both summary and history. Full text is not persisted by these receipts.
- Provider-reported usage belongs to the attempt terminal record, not the local
  estimate. Missing reported usage remains null.
- Receipts omit endpoint URLs, credentials, prompt text, tool arguments/results,
  and summary text. API parsers and storage enforce exact metadata allowlists.

Verification: backend focused suites and contract 95 passed; frontend 42 passed;
TypeScript passed. Final rendered diagnostics, export, and broader regression
remain required in phase 4. No deployment, version bump, or push.
