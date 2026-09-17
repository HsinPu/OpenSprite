import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { getResponseModeResolution, isReasoningResolution, responseModes, type ReasoningResolution } from "../src/api/responseModes";
import { ResponseModeHint, responseModeResolutionText } from "../src/features/ai-settings/ResponseModeHint";
import { createTranslator } from "../src/i18n/catalog";

afterEach(() => vi.unstubAllGlobals());

it("keeps all six ordered levels translated in Chinese and English", () => {
  expect(responseModes.map(mode => createTranslator("zh-TW")(`models.response.${mode}`))).toEqual(["低", "中", "高", "極高", "最高", "極致"]);
  expect(responseModes.map(mode => createTranslator("en")(`models.response.${mode}`))).toEqual(["Low", "Medium", "High", "Extra High", "Max", "Ultra"]);
});

it("uses an encoded read-only preview and rejects a mismatched decision", async () => {
  const decision = { requested: "ultra", effective: "max", status: "fallback" };
  const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify(decision)));
  vi.stubGlobal("fetch", fetch);
  const signal = new AbortController().signal;
  await expect(getResponseModeResolution("openrouter", "vendor/model:free", "ultra", signal)).resolves.toEqual(decision);
  expect(fetch).toHaveBeenCalledWith("/api/settings/ai/response-mode?providerId=openrouter&modelId=vendor%2Fmodel%3Afree&responseMode=ultra", { signal });
  await expect(getResponseModeResolution("openai", "gpt-5.6", "low", signal)).rejects.toThrow("invalid_response_mode_resolution");
});

it.each([
  { requested: "ultra", effective: "ultra", status: "exact" },
  { requested: "medium", effective: "high", status: "unknown" },
  { requested: "medim", effective: null, status: "unknown" },
  { requested: "max", effective: null, status: "exact" },
  { requested: "max", effective: null, status: "unknown", secret: "unexpected" },
])("rejects invalid resolution payloads: %j", value => expect(isReasoningResolution(value)).toBe(false));

it("distinguishes a fallback from unavailable or unknown effort control", () => {
  const t = createTranslator("en");
  expect(responseModeResolutionText({ requested: "ultra", effective: "max", status: "fallback" }, t)).toContain("highest supported level");
  expect(responseModeResolutionText({ requested: "low", effective: "low", status: "exact" }, t)).toContain("Low");
  expect(responseModeResolutionText({ requested: "ultra", effective: null, status: "provider_default" }, t)).not.toEqual(responseModeResolutionText({ requested: "ultra", effective: null, status: "unknown" }, t));
});

it("discards stale model previews and explains request failure", async () => {
  let finishOld!: (response: Response) => void;
  const fetch = vi.fn()
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ requested: "ultra", effective: "high", status: "fallback" })))
    .mockRejectedValueOnce(new Error("offline"));
  vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<ResponseModeHint providerId="openai" modelId="first" mode="ultra" />);
  rerender(<ResponseModeHint providerId="openai" modelId="second" mode="ultra" />);
  const t = createTranslator("zh-TW");
  const latest: ReasoningResolution = { requested: "ultra", effective: "high", status: "fallback" };
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe(responseModeResolutionText(latest, t)));
  await act(async () => finishOld(new Response(JSON.stringify({ requested: "ultra", effective: "max", status: "fallback" }))));
  expect(screen.getByRole("status").textContent).toBe(responseModeResolutionText(latest, t));
  rerender(<ResponseModeHint providerId="openai" modelId="third" mode="ultra" />);
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe(t("models.response.unavailable")));
});
