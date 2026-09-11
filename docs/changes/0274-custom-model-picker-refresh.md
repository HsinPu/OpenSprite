# Custom provider refresh in the model picker

- LiteLLM and other custom providers now expose the same small refresh control
  beside the model selector as OpenRouter.
- Remove the duplicate refresh item from the provider menu; model management stays.
- Fetch the latest provider revision before discovery; ignore stale completions
  after switching providers or unmounting and prevent repeated clicks.
- Keep model selection and budgets unchanged. The backend's existing merge keeps
  manually configured capacities. No default capacity or credential changes.
- Preserve the previous catalog on failed reload, and synchronize the management
  dialog catalog after a successful discovery.
- Custom providers without models remain selectable so discovery can populate them.

No version bump, commit, or local installation is included. OpenAI/Anthropic UI
integration remains a separate unfinished scope.

## Verification

- SettingsPage, CustomProviderCreate, useProviderCatalog: 44 frontend tests passed.
- Existing custom-provider service regressions: 4 passed, including preserving
  manual model metadata when discovered IDs change.
- Typecheck, production build, and diff check passed. Existing build chunk-size
  warnings and jsdom pseudo-element warnings remain.
- No installed-runtime or live provider calls were performed.
