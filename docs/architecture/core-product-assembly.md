# Core and product installation boundary

`opensprite-backend` without extras installs the SDK, execution core and
storage/transport protocols without third-party runtime dependencies. Package
initializers never import the HTTP app or product management implementations.
An embedded caller must explicitly provide a RunPreparation, Loop factory,
gateway and repository. Pure endpoint/workspace records remain available as
non-secret shared data; management services are not loaded by the core.

The `app` extra assembles the complete OpenSprite product: HTTP runtime,
encrypted credentials, local authentication, Provider connection/management,
workspace management, optional Prompt recording, wheel review/deployment and
the official `opensprite-standard-loop==0.2.0` distribution. These facilities
are composed by `runtime.py`, not selected by the execution engine.

Repository product development uses `uv sync --extra app --dev`. Every product
`uv run` also selects `--extra app` so synchronization cannot remove installed
product dependencies. Docker and both installers explicitly request this extra;
the lockfile still pins the complete product installation. Core wheel consumers
install the plain wheel; its default requirements list is empty. A clean offline
venv verification performs normal dependency resolution without `--no-deps`,
executes a dynamic Host/SQLite Run, and then installs the unchanged v5 author
example wheel and executes its three-step draft/review/answer flow.

Public SDK v5 remains `opensprite_backend.agent.plugin`, with the same golden
contract and required pinned System Prompt prefix. This is an import/dependency
boundary, not process isolation or a Python security sandbox. The full product
keeps its existing single writer, AppPaths and encrypted credential boundaries.
