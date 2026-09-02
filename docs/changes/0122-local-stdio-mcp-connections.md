# Local stdio MCP connections

## Scope

- Add the official Python MCP SDK v2 Client dependency and constrain the tested
  backend runtime to Python 3.12 and 3.13.
- Add strict schema-v1 `config/mcp.json`, local stdio Server CRUD, explicit
  test/start/stop lifecycle, protocol negotiation, bounded Tool discovery, and
  deterministic canonical Tool ids.
- Require absolute existing executable and working-directory paths, reject
  symlink endpoints, pass arguments without a shell, and keep new or edited
  configurations disabled until explicit start.
- Add `contracts/mcp-connections.openapi.json` and exact contract tests.

## Verification

- Official SDK fixture initialization, discovery, call and process lifecycle.
- Separate HTTP request tasks can start, discover and stop one session because
  a dedicated owner task retains the SDK transport's cancel-scope ownership.
- Lazy strict storage, same-origin API, inert create, prior-explicit-start
  autostart, tampered path rejection and bounded discovery tests.
