# Streamable HTTP MCP settings UI

## Scope

- Add a typed transport selector to the MCP Server editor.
- Show only executable/arguments/working-directory fields for stdio and only a
  credential-free endpoint URL for Streamable HTTP.
- Use transport-specific Start/Stop or Connect/Disconnect labels and show the
  exact command or endpoint before save and activation.
- Add Traditional Chinese, English and Japanese safety, authentication and
  network error copy.

The complete frontend suite passed 219 tests, plus typecheck and production
build. Installed-runtime browser verification covered inert save, endpoint
confirmation, Connect, discovery, per-call approval, result display and a
390px settings surface without horizontal overflow or console errors.
