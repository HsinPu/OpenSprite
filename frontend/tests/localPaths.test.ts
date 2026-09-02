import { afterEach, describe, expect, it, vi } from "vitest";

import { LocalPathApiError, pickLocalPath } from "../src/api/localPaths";


afterEach(() => vi.unstubAllGlobals());

describe("local path picker API", () => {
  it("returns one strict selected path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ path: "C:\\Tools\\server.exe" })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(pickLocalPath("executable")).resolves.toBe("C:\\Tools\\server.exe");
    expect(fetchMock).toHaveBeenCalledWith("/api/local-paths/pick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "executable" }),
    });
  });

  it("maps cancellation to null", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(pickLocalPath("directory")).resolves.toBeNull();
  });

  it("rejects unknown response fields and maps fixed errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ path: "/tmp/tool", extra: true })),
    ));
    await expect(pickLocalPath("executable")).rejects.toBeInstanceOf(LocalPathApiError);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "picker_busy", message: "private", retryable: true } }), { status: 409 }),
    ));
    await expect(pickLocalPath("directory")).rejects.toMatchObject({ code: "picker_busy" });
  });
});
