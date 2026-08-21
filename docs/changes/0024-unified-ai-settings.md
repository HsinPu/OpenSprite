# 0024 - Unified AI settings contract

## Summary

Replaced the model-only settings boundary with one atomic AI settings contract
that persists the nullable model selection and response mode together.

## Changes

- Added strict `GET` and `PUT /api/settings/ai` operations.
- Added the `fast`, `balanced`, and `deep` response modes, with `balanced` as
  the side-effect-free default when no settings file exists.
- Replaced settings schema v1 with strict schema v2 containing `model` and
  `responseMode`; old schema and old routes are intentionally unsupported.
- Kept connected-Provider validation for non-null model selections while model
  clearing preserves the response mode.
- Removed the old model-selection module and OpenAPI document without aliases.

## Verification

- `python -m pytest -W error --basetemp .pytest-tmp tests/test_ai_settings.py tests/test_app_contract.py -q`
- All tests use temporary `AppPaths`; live `.opensprite` data is not modified.
