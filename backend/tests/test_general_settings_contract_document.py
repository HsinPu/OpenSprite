"""Static checks for the authoritative general settings contract."""

import json
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "general-settings.openapi.json"


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_has_only_approved_operations_and_values() -> None:
    contract = load_contract()
    assert contract["openapi"] == "3.1.0"
    paths = contract["paths"]  # type: ignore[index]
    assert set(paths) == {"/api/settings/general"}  # type: ignore[arg-type]
    assert {key for key in paths["/api/settings/general"] if key in {"get", "put", "post", "delete", "patch"}} == {"get", "put"}  # type: ignore[index]
    schemas = contract["components"]["schemas"]  # type: ignore[index]
    settings = schemas["GeneralSettings"]
    assert settings["additionalProperties"] is False
    assert settings["required"] == ["locale", "timeZone"]
    assert schemas["Locale"]["enum"] == ["zh-TW", "en", "ja"]
    assert schemas["TimeZone"]["enum"] == ["system", "Asia/Taipei", "UTC"]
    assert schemas["ErrorCode"]["enum"] == ["invalid_request", "settings_store_unavailable", "internal_error"]


def test_put_error_mapping_is_explicit() -> None:
    contract = load_contract()
    responses = contract["paths"]["/api/settings/general"]["put"]["responses"]  # type: ignore[index]
    assert responses["400"]["$ref"].endswith("/InvalidRequest")
    assert responses["503"]["$ref"].endswith("/SettingsStoreUnavailable")
    assert responses["500"]["$ref"].endswith("/InternalError")
