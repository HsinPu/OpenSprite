import { normalizePermissionsSettings, serializeProfileOverrides, splitPermissionList, syncPermissionsForm } from "./permissionsDefaults";

export function usePermissionsSettingsActions({ settingsState, requestSettingsJson, copy, setSettingsSuccess }) {
  async function loadPermissionsSettings() {
    settingsState.permissionsLoading = true;
    settingsState.permissionsError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/permissions");
      settingsState.permissions = normalizePermissionsSettings(payload.permissions || {});
      syncPermissionsForm(settingsState);
      await loadHarnessPolicyPreview();
    } catch (error) {
      settingsState.permissionsError = error?.message || copy.value.notices.permissionsLoadFailed;
    } finally {
      settingsState.permissionsLoading = false;
    }
  }

  async function loadHarnessPolicyPreview() {
    settingsState.harnessPolicyPreviewLoading = true;
    settingsState.harnessPolicyPreviewError = "";
    try {
      const payload = await requestSettingsJson("/api/settings/harness-policy-preview");
      settingsState.harnessPolicyPreview = payload.harness_policy_preview || { rows: [], user_permissions: null };
    } catch (error) {
      settingsState.harnessPolicyPreviewError = error?.message || copy.value.notices.permissionsLoadFailed;
    } finally {
      settingsState.harnessPolicyPreviewLoading = false;
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
          profile_overrides: serializeProfileOverrides(settingsState.permissionsForm.profileOverrides),
        }),
      });
      settingsState.permissions = normalizePermissionsSettings(payload.permissions || {});
      syncPermissionsForm(settingsState);
      await loadHarnessPolicyPreview();
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
    loadHarnessPolicyPreview,
    savePermissionsSettings,
  };
}
