# Complete schedule OpenAPI detail

## Objective

Make the schedule contract independently usable instead of documenting only
route names.

## Changes

- Added authenticated Cookie Session security, path/query parameters, request
  bodies, status responses, cadence unions, execution profiles, schedule and
  occurrence payloads, pagination, runtime continuity, and safe errors.
- Kept all objects closed to unknown properties and aligned operation IDs with
  generated FastAPI routes.

## Verification

Static contract checks validate route parity, strict schemas, latest occurrence,
continuity values, and authentication declaration.
