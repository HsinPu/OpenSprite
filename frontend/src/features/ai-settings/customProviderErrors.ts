import type { Translator } from "../../i18n/catalog";

export function customProviderErrorText(code: string, t: Translator): string {
  switch (code) {
    case "invalid_request": case "credential_required": case "invalid_credentials":
    case "duplicate_name": case "duplicate_model":
      return t("models.custom.error.invalid");
    case "revision_conflict": case "provider_not_found": case "model_not_found":
      return t("models.custom.error.conflict");
    case "provider_busy": return t("models.custom.error.busy");
    case "provider_in_use": return t("models.custom.error.inUse");
    case "model_discovery_unsupported": return t("models.custom.error.discovery");
    case "network_error": case "provider_unreachable": case "provider_timeout":
    case "provider_rate_limited": case "not_connected":
      return t("models.custom.error.connection");
    default: return t("models.custom.error.unknown");
  }
}
