export type AppInfo = {
  version: string;
  revision: string;
  buildType: "development" | "installed";
  dirty: boolean;
  installedAt: string | null;
};

export class AppInfoApiError extends Error {
  constructor() { super("app_info_unavailable"); this.name = "AppInfoApiError"; }
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, expected: readonly string[]) => Object.keys(value).length === expected.length && Object.keys(value).every((key) => expected.includes(key));
const versionPattern = /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/;
const revisionPattern = /^(?:[0-9a-f]{7,40}|development|unknown)$/;

export async function getAppInfo(): Promise<AppInfo> {
  let response: Response;
  try { response = await fetch("/api/app-info"); } catch { throw new AppInfoApiError(); }
  if (response.status !== 200) throw new AppInfoApiError();
  let value: unknown;
  try { value = await response.json(); } catch { throw new AppInfoApiError(); }
  if (!record(value) || !exactKeys(value, ["version", "revision", "buildType", "dirty", "installedAt"])
    || typeof value.version !== "string" || !versionPattern.test(value.version)
    || typeof value.revision !== "string" || !revisionPattern.test(value.revision)
    || !["development", "installed"].includes(String(value.buildType))
    || typeof value.dirty !== "boolean"
    || (value.installedAt !== null && (typeof value.installedAt !== "string" || Number.isNaN(Date.parse(value.installedAt))))) throw new AppInfoApiError();
  return value as AppInfo;
}
