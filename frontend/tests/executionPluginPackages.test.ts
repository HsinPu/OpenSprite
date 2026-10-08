import { afterEach, describe, expect, it, vi } from "vitest";
import { AUTHENTICATION_REQUIRED_EVENT } from "../src/api/http";
import { ExecutionPackageApiError, MAX_EXECUTION_PACKAGE_BYTES, downloadExecutionDeployment, getExecutionPackages, importExecutionPackage, removeExecutionPackage } from "../src/api/executionPluginPackages";

const id = "064c4419-443f-4d30-a2e9-eab8cbd03712";
const sample = { packages: [{ id, fileName: "example-0.1.0-py3-none-any.whl", distributionName: "example", version: "0.1.0", sha256: "a".repeat(64), sizeBytes: 2000,
  importedAt: "2026-10-08T01:02:03+00:00", requiresPython: ">=3.12", requiresDist: ["opensprite-backend>=0.21.27,<0.22"],
  plugins: [{ id: "example", kind: "loop", apiVersion: 2, entryPoint: "example.plugin:factory" }], runtimeStatus: "not_installed" }],
  runtime: { kind: "docker", baseImage: "opensprite:local", manifestStatus: "missing" } };
const body = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => vi.unstubAllGlobals());

describe("execution package API", () => {
  it("reads after an import finishes when settings reopen during upload", async () => {
    let finish!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => { finish = resolve; });
    const fetchMock = vi.fn().mockReturnValueOnce(pending).mockResolvedValueOnce(body(sample));
    vi.stubGlobal("fetch", fetchMock);
    const importing = importExecutionPackage(new File(["wheel"], sample.packages[0].fileName));
    const reading = getExecutionPackages();
    expect(fetchMock).toHaveBeenCalledOnce();
    finish(body(sample));
    await importing;
    await expect(reading).resolves.toEqual(sample);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it("keeps imported status distinct from deployment confirmation and sends bounded multipart", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(body(sample)).mockResolvedValueOnce(body(sample));
    vi.stubGlobal("fetch", fetchMock);
    expect(await getExecutionPackages()).toEqual(sample);
    const file = new File(["wheel"], sample.packages[0].fileName);
    expect(await importExecutionPackage(file)).toEqual(sample);
    const init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.headers).toBeUndefined(); // browser supplies the multipart boundary
    expect((init.body as FormData).get("file")).toBe(file);
  });
  it.each(["id", "sha256"])("rejects duplicate package %s rather than displaying an ambiguous identity", async (field) => {
    const item = { ...sample.packages[0], id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", sha256: "b".repeat(64), [field]: sample.packages[0][field as "id" | "sha256"] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(body({ ...sample, packages: [sample.packages[0], item] })));
    await expect(getExecutionPackages()).rejects.toMatchObject({ code: "malformed_response" });
  });
  it("rejects unsupported API metadata and unknown runtime statuses", async () => {
    const changed = { ...sample, packages: [{ ...sample.packages[0], runtimeStatus: "installed" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(body(changed)).mockResolvedValueOnce(body({ ...sample, packages: [{ ...sample.packages[0], plugins: [{ ...sample.packages[0].plugins[0], apiVersion: 0 }] }] })));
    await expect(getExecutionPackages()).rejects.toMatchObject({ code: "malformed_response" });
    await expect(getExecutionPackages()).rejects.toMatchObject({ code: "malformed_response" });
  });
  it("removes only the cache ID and validates the downloaded MIME type", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response("zip", { headers: { "Content-Type": "application/zip" } }))
      .mockResolvedValueOnce(new Response("html", { headers: { "Content-Type": "text/html" } }));
    vi.stubGlobal("fetch", fetchMock);
    await removeExecutionPackage(id);
    expect(fetchMock).toHaveBeenNthCalledWith(1, `/api/execution-plugin-packages/${id}`, { method: "DELETE" });
    expect((await downloadExecutionDeployment(id)).size).toBe(3);
    await expect(downloadExecutionDeployment(id)).rejects.toMatchObject({ code: "malformed_response" });
  });
  it("rejects over-limit files and malformed IDs before making a request", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    const file = new File(["wheel"], "example.whl"); Object.defineProperty(file, "size", { value: MAX_EXECUTION_PACKAGE_BYTES + 1 });
    await expect(importExecutionPackage(file)).rejects.toMatchObject({ code: "package_too_large" });
    await expect(removeExecutionPackage("../auth.json")).rejects.toMatchObject({ code: "invalid_request" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("propagates safe server errors and authentication expiry", async () => {
    const listener = vi.fn(); window.addEventListener(AUTHENTICATION_REQUIRED_EVENT, listener);
    try {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(body({ error: { code: "invalid_package", message: "Invalid wheel", retryable: false } }, 400))
        .mockResolvedValueOnce(body({ error: { code: "invalid_request", message: "Auth required", retryable: false } }, 401)));
      await expect(getExecutionPackages()).rejects.toEqual(new ExecutionPackageApiError("invalid_package"));
      await expect(getExecutionPackages()).rejects.toMatchObject({ code: "malformed_response" });
      expect(listener).toHaveBeenCalledOnce();
    } finally { window.removeEventListener(AUTHENTICATION_REQUIRED_EVENT, listener); }
  });
});
