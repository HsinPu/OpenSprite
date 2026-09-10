# Model catalog refresh control

- Add an Ant Design refresh control above model selection for connected OpenRouter selections.
- Call the existing forced catalog reload, with loading and disabled states during refresh and credential operations. Preserve existing refresh error reporting and selection reconciliation.
- Keep built-in OpenAI/Anthropic catalogs unchanged; do not imply those catalogs support remote fetching.
- Include Traditional Chinese, English, and Japanese labels and a regression for refreshing an already cached list, preserving selection, and exposing new models.
- Inspected the installed AI-model settings page in the in-app browser. The installed runtime was not updated; no version bump, commit, or push in this slice.
- Verification: 31 SettingsPage tests passed; production build including TypeScript check and git diff check passed. Existing build chunk-size warning remains.
