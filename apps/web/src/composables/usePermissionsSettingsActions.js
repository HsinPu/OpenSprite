import { normalizePermissionsSettings, splitPermissionList, syncPermissionsForm } from "./permissionsDefaults";

export function usePermissionsSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function loadPermissionsSettings() {
    settingsState.permissionsLoading = true;
    settingsState.permissionsError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/permissions");
      settingsState.permissions = normalizePermissionsSettings(payload.permissions || {});
      syncPermissionsForm(settingsState);
      await loadToolAccessPreview();
    } catch (error) {
      settingsState.permissionsError = error?.message || copy.value.notices.permissionsLoadFailed;
    } finally {
      settingsState.permissionsLoading = false;
    }
  }

  async function loadToolAccessPreview() {
    settingsState.toolAccessPreviewLoading = true;
    settingsState.toolAccessPreviewError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/tool-access-preview");
      settingsState.toolAccessPreview = payload.tool_access_preview || { rows: [], user_permissions: null };
    } catch (error) {
      settingsState.toolAccessPreviewError = error?.message || copy.value.notices.permissionsLoadFailed;
    } finally {
      settingsState.toolAccessPreviewLoading = false;
    }
  }

  async function savePermissionsSettings() {
    settingsState.permissionsLoading = true;
    settingsState.permissionsError = "";
    settingsState.permissionsNotice = "";
    try {
      const payload = await requestSettingsJson("/api/settings/permissions", {
        method: "PUT",
        body: JSON.stringify({
          enabled: settingsState.permissionsForm.enabled,
          approval_mode: settingsState.permissionsForm.approvalMode || null,
          approval_timeout_seconds: settingsState.permissionsForm.approvalTimeoutSeconds,
          allowed_tools: splitPermissionList(settingsState.permissionsForm.allowedTools),
          denied_tools: splitPermissionList(settingsState.permissionsForm.deniedTools),
          allowed_risk_levels: settingsState.permissionsForm.allowedRiskLevels,
          denied_risk_levels: settingsState.permissionsForm.deniedRiskLevels,
          approval_required_tools: splitPermissionList(settingsState.permissionsForm.approvalRequiredTools),
          approval_required_risk_levels: settingsState.permissionsForm.approvalRequiredRiskLevels,
        }),
      });
      settingsState.permissions = normalizePermissionsSettings(payload.permissions || {});
      syncPermissionsForm(settingsState);
      await loadToolAccessPreview();
      setSettingsSuccess(
        "permissionsNotice",
        payload.restart_required ? copy.value.notices.permissionsRestartRequired : copy.value.notices.permissionsSaved,
      );
    } catch (error) {
      settingsState.permissionsError = error?.message || copy.value.notices.permissionsSaveFailed;
    } finally {
      settingsState.permissionsLoading = false;
    }
  }

  return {
    loadPermissionsSettings,
    loadToolAccessPreview,
    savePermissionsSettings,
  };
}
