# Agents settings single heading

Removed the duplicate outer Agents title and introduction from SettingsPage.
AgentsSettings owns its heading, description and master switch, matching the
existing Skills composition. No API, policy or version changes are included.

The regression renders the complete SettingsPage with the real AgentsSettings
component. Before the fix it finds two headings; after the fix it requires exactly
one heading, one introduction and the existing master switch.

Verification: 35 related component tests passed; TypeScript and production build
passed. The installed runtime has not been updated by this source-code fix.
