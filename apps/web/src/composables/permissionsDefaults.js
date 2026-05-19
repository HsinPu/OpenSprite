const DEFAULT_RISK_LEVELS = ["read", "write", "execute", "network", "external_side_effect", "configuration", "delegation", "memory", "mcp"];

export function createDefaultPermissionsState() {
  return {
    enabled: true,
    approval_mode: "",
    approval_timeout_seconds: 300,
    allowed_tools: ["*"],
    denied_tools: [],
    allowed_risk_levels: [...DEFAULT_RISK_LEVELS],
    denied_risk_levels: [],
    approval_required_tools: [],
    approval_required_risk_levels: [],
    risk_level_options: [...DEFAULT_RISK_LEVELS],
    approval_mode_options: ["ask", "auto", "block"],
  };
}

export function createDefaultPermissionsForm() {
  return {
    enabled: true,
    approvalMode: "",
    approvalTimeoutSeconds: 300,
    allowedTools: "*",
    deniedTools: "",
    allowedRiskLevels: [...DEFAULT_RISK_LEVELS],
    deniedRiskLevels: [],
    approvalRequiredTools: "",
    approvalRequiredRiskLevels: [],
  };
}

export function normalizePermissionsSettings(value) {
  const defaults = createDefaultPermissionsState();
  const payload = value && typeof value === "object" ? value : {};
  const riskOptions = normalizeList(payload.risk_level_options || payload.riskLevelOptions || defaults.risk_level_options);
  return {
    ...defaults,
    enabled: payload.enabled !== false,
    approval_mode: String(payload.approval_mode ?? payload.approvalMode ?? "").trim(),
    approval_timeout_seconds: positiveNumber(payload.approval_timeout_seconds ?? payload.approvalTimeoutSeconds, defaults.approval_timeout_seconds),
    allowed_tools: normalizeList(payload.allowed_tools || payload.allowedTools || defaults.allowed_tools),
    denied_tools: normalizeList(payload.denied_tools || payload.deniedTools),
    allowed_risk_levels: normalizeList(payload.allowed_risk_levels || payload.allowedRiskLevels || defaults.allowed_risk_levels),
    denied_risk_levels: normalizeList(payload.denied_risk_levels || payload.deniedRiskLevels),
    approval_required_tools: normalizeList(payload.approval_required_tools || payload.approvalRequiredTools),
    approval_required_risk_levels: normalizeList(payload.approval_required_risk_levels || payload.approvalRequiredRiskLevels),
    risk_level_options: riskOptions.length ? riskOptions : defaults.risk_level_options,
    approval_mode_options: normalizeList(payload.approval_mode_options || payload.approvalModeOptions || defaults.approval_mode_options),
  };
}

export function syncPermissionsForm(settingsState) {
  const permissions = settingsState.permissions || createDefaultPermissionsState();
  settingsState.permissionsForm.enabled = permissions.enabled;
  settingsState.permissionsForm.approvalMode = permissions.approval_mode || "";
  settingsState.permissionsForm.approvalTimeoutSeconds = permissions.approval_timeout_seconds;
  settingsState.permissionsForm.allowedTools = permissions.allowed_tools.join("\n");
  settingsState.permissionsForm.deniedTools = permissions.denied_tools.join("\n");
  settingsState.permissionsForm.allowedRiskLevels = [...permissions.allowed_risk_levels];
  settingsState.permissionsForm.deniedRiskLevels = [...permissions.denied_risk_levels];
  settingsState.permissionsForm.approvalRequiredTools = permissions.approval_required_tools.join("\n");
  settingsState.permissionsForm.approvalRequiredRiskLevels = [...permissions.approval_required_risk_levels];
}

export function splitPermissionList(value) {
  return String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return splitPermissionList(value);
  }
  return [];
}

function positiveNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}
