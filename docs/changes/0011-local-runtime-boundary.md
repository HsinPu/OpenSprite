# 0011 - Secured local runtime boundary

## Objective

Activate the approved provider runtime behind a loopback-only HTTP trust
boundary without changing provider paths, payloads, public errors, or the
injectable `create_app()` default used by existing clients and tests.

## Vulnerability and trust boundary

Before this slice, `create_provider_runtime()` existed but no production ASGI
composition owned its client lifecycle, and the application had no Host or
browser Origin enforcement. An initial composition attempt also created one
runtime at app construction and captured it across lifespan re-entry, allowing
a later entry to serve through the previously closed client. If provider routes
had been launched directly, any local or browser-reachable caller that could
reach the port could supply an arbitrary Host, and a cross-origin page could
attempt credential mutations.
The affected assets were OS-stored provider credentials, non-secret provider
metadata, provider validation traffic, and availability of the single-user
desktop service. Exploitation required network reachability to the local HTTP
port; cross-origin mutation additionally required a victim browser able to
send the request.

The enforcement point is ASGI middleware on the secured system app, before
route dependency resolution or request-body parsing. The launch boundary is
the documented uvicorn factory invocation. Provider services remain unaware
of transport headers, so every current and future HTTP path in the secured app
shares the same policy.

## Security invariant and code changes

- `create_app()` now accepts explicit lifespan and local-security inputs while
  retaining its injectable, unsecured-by-default test composition and
  fail-closed provider dependency.
- `LocalRequestSecurityMiddleware` requires exactly one syntactically strict
  Host whose canonical hostname is `localhost`, `127.0.0.1`, or `::1`.
  Userinfo, control/non-ASCII bytes, paths, aliases, alternate IP encodings,
  malformed IPv6, invalid ports, and duplicate or combined values fail closed.
- `POST`, `PUT`, `PATCH`, and `DELETE` require exactly one serialized HTTP(S)
  Origin. Canonical scheme, hostname, and effective port must match the request
  scheme and Host. Missing, opaque, wildcard, multiple, userinfo-bearing,
  path/query/fragment-bearing, downgraded, or otherwise mismatched values are
  rejected. There is no CORS or Referer fallback.
- Security failures reuse the existing fixed `invalid_request` envelope and
  status 400 through an injected response factory. No rejected value is
  echoed or logged, and provider handlers are not called.
- Importing or calling `create_system_app()` remains offline and leaves provider
  access bound to `UnavailableProviderConnections`. Every lifespan entry uses
  `create_provider_runtime()` to create and bind one fresh runtime, then unbinds
  before closing that entry's client exactly once. Factory/startup failure never
  serves; close failure propagates after unbinding and permits a later fresh
  entry. A non-blocking per-app guard rejects concurrent lifespan entry before
  it can serve, so a closed client cannot be rebound.
- The launch command binds only `127.0.0.1` and uses `--no-proxy-headers`.
  `X-Forwarded-*` is not trusted. Vite must retain the original same-origin
  Host and Origin with `changeOrigin: false`, including exact canonical port
  equality.
- No dependency, contract, provider, keyring, state, frontend, installer, or
  public route/payload change was required. No environment API-key fallback,
  log statement, project CLI, or server process was added.

## Verification

All tests use ASGI calls, FastAPI `TestClient`, fake provider connections, and
an injected fake runtime. They perform no real provider request or keyring
operation and launch no server process. Final evidence on Windows, Python
3.12.13:

- focused Host/Origin/runtime suite: **66 passed**;
- full backend suite with warnings as errors: **206 passed**;
- `python -m compileall -q src tests`: passed;
- `uv lock --check --offline`: passed with the existing lock and no dependency
  changes;
- `uv pip check`: all installed packages compatible;
- security source scan: no header/API-key logging, CORS middleware,
  environment API-key fallback, or trusted-proxy path was introduced; and
- `git diff --check`: passed.

No dedicated SAST or dependency-vulnerability scanner is configured, so no
broader scanning result is claimed.

## Compatibility, rollout, and incident follow-up

Existing `create_app()` callers keep their previous behavior; only the system
factory enables the new transport policy. System-app construction no longer
selects keyring or constructs an HTTP client; lifecycle entry is the sole
runtime ownership point. Provider paths, request/response models, status
mappings, and stable error envelopes are unchanged. The Vite proxy must use
`changeOrigin: false`; changing Host to the backend port while preserving the
browser Origin will correctly fail the same-origin check.

Packaging and installers must invoke the documented factory, retain the
`127.0.0.1` bind and `--no-proxy-headers`, and stop rollout on any deviation.
Monitor only aggregate fixed error codes and operation counts; never record
Host, Origin, forwarded headers, request bodies, API keys, provider bodies, or
exception text. A rise in `invalid_request` may indicate proxy misconfiguration
or attempted boundary bypass and should be investigated with non-sensitive
metadata only.

No credentials were used or exposed by this implementation and its tests, so
credential rotation and incident response are not required. If deployment
logs or prior runtime evidence show the provider routes were reachable without
these controls, treat that as a separate incident: establish exposure dates,
review non-sensitive access telemetry, notify affected users, and rotate
provider credentials according to the incident decision.
