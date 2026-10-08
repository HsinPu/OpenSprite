# OpenSprite local data layout

Windows `%USERPROFILE%\.opensprite` and Linux `~/.opensprite` are the sole user-data roots, resolved by `AppPaths`.
Installation files and Python/frontend dependencies live elsewhere. The complete data root is sensitive.

| Path within root | Purpose |
| --- | --- |
| auth.json + config/credential.key | AES-256-GCM credentials and the per-installation random key; always backed up/restored together |
| config/settings.json | AI model, budgets, mode, continuation/delivery and prompt logging; new schema v11 |
| config/execution.json | Loop/policy default IDs, settings schema v1; runtime plugin API v2 |
| config/providers.json | Custom Provider/model catalog without plaintext credentials |
| config/general.json + config/conversation.json | Locale/time zone and conversation UI preferences |
| config/workspaces.json | Managed Workspace/mount metadata and active selection |
| config/access-policy.json + config/access.json | Installation access policy and password verifier |
| data/opensprite.db | Conversations, messages, Runs, events and compactions; fresh schema v21 has five tables |
| workspace/ | Managed project scopes and Default Workspace |
| state/ | Credential/catalog journals and short-lived bootstrap state |
| logs/system-prompts + logs/model-requests | Sensitive prompt/request diagnostics when required or explicitly enabled |
| cache/execution-plugin-packages | Reviewed imported wheels and static metadata |
| cache/workspace-relocation | Verified migration staging; failed copies retained |

Paths do not create unused reserved directories. Credentials are persisted only after validation; optional settings/cache/logs are created on actual writes.
Workspace startup creates only its required managed scopes.
Public events contain hashes/IDs and sanitized data instead of full paths, prompts or credentials. Full prompt logs remain sensitive.

The clean core does not read or execute retired Tools/Skills/Agents/MCP/schedule configuration.
Existing directories, extra SQLite tables and encrypted entries stay on disk; they are not automatically deleted or activated.
The v20→v21 upgrade preserves data. Earlier SQLite versions must first upgrade through 0.21.30.
Read projection skips retired events and old receipt/execution interfaces; original rows remain available in a protected backup.
Provider writes preserve opaque retired encrypted entries; public credential operations reject their IDs.

Default uninstall preserves the entire data root. Explicitly confirmed full uninstall removal includes any historical contents.
One backend process writes a root; do not share it between desktop and containers or multiple Uvicorn workers.
