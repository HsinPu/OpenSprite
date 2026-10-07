import { apiFetch } from "./http";

export const MAX_EXECUTION_PACKAGE_BYTES = 10 * 1024 * 1024;
export type ExecutionPackagePlugin = { id: string; kind: "loop" | "policy"; apiVersion: number; entryPoint: string };
export type ExecutionPackage = {
  id: string; fileName: string; distributionName: string; version: string; sha256: string;
  sizeBytes: number; importedAt: string; requiresPython: string | null; requiresDist: string[];
  plugins: ExecutionPackagePlugin[]; runtimeStatus: "not_installed" | "confirmed" | "unverified" | "mismatch";
};
export type ExecutionPackageCatalog = {
  packages: ExecutionPackage[];
  runtime: { kind: "docker" | "local"; baseImage: string | null; manifestStatus: "verified" | "missing" | "invalid" };
};
export type ExecutionPackageErrorCode = "invalid_request" | "invalid_package" | "incompatible_package" | "package_too_large"
  | "package_not_found" | "packages_store_unavailable" | "deployment_unavailable" | "internal_error" | "network_error" | "malformed_response";
export class ExecutionPackageApiError extends Error {
  constructor(readonly code: ExecutionPackageErrorCode) { super(code); this.name = "ExecutionPackageApiError"; }
}
const endpoint = "/api/execution-plugin-packages";
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, keys: readonly string[]) => Object.keys(value).length === keys.length && Object.keys(value).every((key) => keys.includes(key));
const uuid = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
const pluginId = (value: unknown): value is string => typeof value === "string" && /^[a-z][a-z0-9_.-]{0,63}$/.test(value);
const text = (value: unknown, max: number, min = 0): value is string => typeof value === "string" && value.length >= min && value.length <= max;

function catalog(value: unknown): ExecutionPackageCatalog {
  const invalid = () => new ExecutionPackageApiError("malformed_response");
  if (!record(value) || !exactKeys(value, ["packages", "runtime"]) || !Array.isArray(value.packages) || !record(value.runtime)
    || value.packages.length > 64 || !exactKeys(value.runtime, ["kind", "baseImage", "manifestStatus"])
    || !["docker", "local"].includes(String(value.runtime.kind))
    || !(value.runtime.baseImage === null || text(value.runtime.baseImage, 256, 1))
    || !["verified", "missing", "invalid"].includes(String(value.runtime.manifestStatus))) throw invalid();
  const ids = new Set<string>();
  const hashes = new Set<string>();
  const packages = value.packages.map((item: unknown): ExecutionPackage => {
    if (!record(item) || !exactKeys(item, ["id", "fileName", "distributionName", "version", "sha256", "sizeBytes", "importedAt", "requiresPython", "requiresDist", "plugins", "runtimeStatus"])
      || !uuid(item.id) || !text(item.fileName, 255, 1) || !item.fileName.endsWith(".whl") || /[\\/\x00-\x1f]/.test(item.fileName)
      || !text(item.distributionName, 128, 1) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item.distributionName)
      || !text(item.version, 64, 1) || typeof item.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(item.sha256)
      || !Number.isSafeInteger(item.sizeBytes) || Number(item.sizeBytes) < 1 || Number(item.sizeBytes) > MAX_EXECUTION_PACKAGE_BYTES
      || !text(item.importedAt, 64, 1) || !Number.isFinite(Date.parse(item.importedAt))
      || !(item.requiresPython === null || text(item.requiresPython, 256))
      || !Array.isArray(item.requiresDist) || item.requiresDist.length > 64 || !item.requiresDist.every((dep) => text(dep, 512, 1))
      || !Array.isArray(item.plugins) || !item.plugins.length || item.plugins.length > 32
      || !["not_installed", "confirmed", "unverified", "mismatch"].includes(String(item.runtimeStatus))
      || ids.has(item.id) || hashes.has(item.sha256)) throw invalid();
    ids.add(item.id); hashes.add(item.sha256);
    const pluginIds = new Set<string>();
    const plugins = item.plugins.map((point: unknown): ExecutionPackagePlugin => {
      if (!record(point) || !exactKeys(point, ["id", "kind", "apiVersion", "entryPoint"]) || !pluginId(point.id)
        || (point.kind !== "loop" && point.kind !== "policy") || point.apiVersion !== 1
        || !text(point.entryPoint, 256, 1) || pluginIds.has(`${point.kind}:${point.id}`)) throw invalid();
      pluginIds.add(`${point.kind}:${point.id}`);
      return { id: point.id, kind: point.kind, apiVersion: point.apiVersion, entryPoint: point.entryPoint };
    });
    return { id: item.id, fileName: item.fileName, distributionName: item.distributionName, version: item.version, sha256: item.sha256,
      sizeBytes: Number(item.sizeBytes), importedAt: item.importedAt, requiresPython: item.requiresPython,
      requiresDist: item.requiresDist as string[], plugins, runtimeStatus: item.runtimeStatus as ExecutionPackage["runtimeStatus"] };
  });
  return { packages, runtime: value.runtime as ExecutionPackageCatalog["runtime"] };
}
const codes = new Map<number, readonly ExecutionPackageErrorCode[]>([
  [400, ["invalid_request", "invalid_package", "incompatible_package"]], [404, ["package_not_found"]], [413, ["package_too_large"]],
  [503, ["packages_store_unavailable", "deployment_unavailable"]], [500, ["internal_error"]],
]);
async function checkedFetch(url: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try { response = await apiFetch(url, init); } catch { throw new ExecutionPackageApiError("network_error"); }
  if (!response.ok) {
    let value: unknown;
    try { value = await response.json(); } catch { throw new ExecutionPackageApiError("malformed_response"); }
    if (!record(value) || !exactKeys(value, ["error"]) || !record(value.error) || !exactKeys(value.error, ["code", "message", "retryable"])
      || typeof value.error.code !== "string" || !codes.get(response.status)?.includes(value.error.code as ExecutionPackageErrorCode)
      || typeof value.error.message !== "string" || typeof value.error.retryable !== "boolean") throw new ExecutionPackageApiError("malformed_response");
    throw new ExecutionPackageApiError(value.error.code as ExecutionPackageErrorCode);
  }
  return response;
}
async function readCatalog(response: Response): Promise<ExecutionPackageCatalog> {
  if (response.status !== 200) throw new ExecutionPackageApiError("malformed_response");
  let value: unknown;
  try { value = await response.json(); } catch { throw new ExecutionPackageApiError("malformed_response"); }
  return catalog(value);
}
const pendingMutations = new Set<Promise<unknown>>();
async function afterMutations(): Promise<void> {
  while (pendingMutations.size) await Promise.allSettled([...pendingMutations]);
}
function track<T>(write: Promise<T>): Promise<T> {
  pendingMutations.add(write);
  void write.then(() => pendingMutations.delete(write), () => pendingMutations.delete(write));
  return write;
}
export async function getExecutionPackages(): Promise<ExecutionPackageCatalog> {
  await afterMutations();
  return readCatalog(await checkedFetch(endpoint));
}
async function importing(file: File): Promise<ExecutionPackageCatalog> {
  if (file.size > MAX_EXECUTION_PACKAGE_BYTES) throw new ExecutionPackageApiError("package_too_large");
  if (!file.size || !file.name.endsWith(".whl")) throw new ExecutionPackageApiError("invalid_package");
  const body = new FormData(); body.append("file", file);
  return readCatalog(await checkedFetch(endpoint, { method: "POST", body }));
}
export function importExecutionPackage(file: File): Promise<ExecutionPackageCatalog> { return track(importing(file)); }
function packagePath(id: string): string {
  if (!uuid(id)) throw new ExecutionPackageApiError("invalid_request");
  return `${endpoint}/${id}`;
}
async function removing(id: string): Promise<void> {
  const response = await checkedFetch(packagePath(id), { method: "DELETE" });
  if (response.status !== 204) throw new ExecutionPackageApiError("malformed_response");
}
export function removeExecutionPackage(id: string): Promise<void> { return track(removing(id)); }
export async function downloadExecutionDeployment(id: string): Promise<Blob> {
  const response = await checkedFetch(`${packagePath(id)}/deployment-bundle`);
  if (response.status !== 200 || response.headers.get("Content-Type")?.split(";")[0]?.trim() !== "application/zip") throw new ExecutionPackageApiError("malformed_response");
  try { return await response.blob(); } catch { throw new ExecutionPackageApiError("network_error"); }
}
