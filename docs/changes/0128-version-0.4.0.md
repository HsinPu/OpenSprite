# Version 0.4.0

OpenSprite 0.4.0 adds credential-free Streamable HTTP MCP connections while
retaining local stdio, Tool approval and receipt behavior. This change updates
the authoritative backend package, lockfile, build-info expectations, About UI
and Windows installer version. It does not publish a tag or release artifact.

The Windows isolation installer passed. The local installation reports version
0.4.0 and health `ok`; it was built from the current uncommitted Streamable HTTP
working tree and therefore correctly reports the committed 0.3.0 baseline
revision with `dirty=true`. Windows retained one locked rollback directory, so
no manual installation-directory deletion was attempted.
