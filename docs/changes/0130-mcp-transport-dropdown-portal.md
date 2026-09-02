# MCP transport dropdown portal

The MCP transport Select now mounts its Ant Design dropdown inside the owning
settings surface. `SettingsPage` passes the existing modal container through
`ToolsSettings`, preventing the body-level portal from falling outside the
nested settings Modal's pointer interaction layer. A component regression test
proves a pointer selection switches from stdio to Streamable HTTP.
