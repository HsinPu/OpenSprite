import { zipSync } from "fflate";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { SkillsSettings } from "../src/features/settings/SkillsSettings";
import { createTranslator } from "../src/i18n/catalog";
import { getSkill, listSkills, skillRequest, importSkillZip, batchSkills } from "../src/api/skills";

vi.mock("../src/api/skills", async importOriginal => ({ ...await importOriginal<typeof import("../src/api/skills")>(), getSkill: vi.fn(), listSkills: vi.fn(), skillRequest: vi.fn(), importSkillZip: vi.fn(), batchSkills: vi.fn() }));
const content = "---\nname: review\ndescription: Review\n---\nCheck it.";
const skill = { id: "11111111-1111-4111-8111-111111111111", scope: "global" as const, workspaceId: null,
  name: "review", description: "Review", directoryName: "review", revision: 1, enabled: false,
  confirmedHash: null, shadowedBySkillId: null, contentHash: "a".repeat(64), state: "disabled", effective: false, reason: "disabled", content };
const defaultWorkspace = { id: "00000000-0000-4000-8000-000000000000", kind: "default" as const, name: "Default workspace", directoryName: "default", rootPath: "C:\\Users\\Test\\.opensprite\\workspace\\default", mounts: [], availability: "available" as const, unavailableReason: null, revision: 1, createdAt: "1970-01-01T00:00:00Z", updatedAt: "1970-01-01T00:00:00Z", usage: { conversationCount: 0, scheduleCount: 0, activeRunCount: 0 } };
const alphaWorkspace = { ...defaultWorkspace, id: "22222222-2222-4222-8222-222222222222", kind: "managed" as const, name: "Alpha", directoryName: "Alpha" };
const betaWorkspace = { ...defaultWorkspace, id: "33333333-3333-4333-8333-333333333333", kind: "managed" as const, name: "Beta", directoryName: "Beta" };
const workspaceCatalog = { revision: 1, activeWorkspaceId: alphaWorkspace.id, workspaces: [defaultWorkspace, alphaWorkspace, betaWorkspace] };
beforeEach(() => {
  vi.mocked(listSkills).mockReset().mockResolvedValue({ revision: 1, enabled: true, skills: [skill] });
  vi.mocked(getSkill).mockReset().mockResolvedValue({ revision: 1, skill });
  vi.mocked(skillRequest).mockReset().mockResolvedValue({ revision: 2, enabled: true });
  vi.mocked(importSkillZip).mockReset();
  vi.mocked(batchSkills).mockReset().mockResolvedValue({ revision: 2, completed: 1, skipped: [], failed: [] });
});

async function openBatchMenu(action: string) {
  const button = await screen.findByRole("button", { name: "批次操作" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  fireEvent.click(await screen.findByRole("menuitem", { name: action }));
}

it("confirms a scope-bounded batch enable and displays its outcome", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await openBatchMenu("全部啟用");
  expect(screen.getByText("範圍：全域，共 1 個 Skills。")).toBeTruthy();
  expect(batchSkills).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "確認操作" }));
  await waitFor(() => expect(batchSkills).toHaveBeenCalledWith("global", null, "enable", 1));
  expect(await screen.findByText("完成 1 個，略過 0 個，失敗 0 個。")).toBeTruthy();
});

it("requires typed confirmation for archive and cancellation does not mutate", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await openBatchMenu("移除全部");
  const confirm = screen.getByRole("button", { name: "確認操作" }) as HTMLButtonElement;
  expect(confirm.disabled).toBe(true);
  fireEvent.change(screen.getByRole("textbox", { name: "請輸入「移除」確認" }), { target: { value: "移除" } });
  expect(confirm.disabled).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: /取\s*消/ }));
  expect(batchSkills).not.toHaveBeenCalled();
});

it("uses the current workspace and prevents duplicate batch submission", async () => {
  let finish: (() => void) | undefined;
  vi.mocked(batchSkills).mockImplementation(() => new Promise(resolve => { finish = () => resolve({ revision: 2, completed: 1, skipped: [], failed: [] }); }));
  render(<SkillsSettings workspaces={{ catalog: workspaceCatalog }} container={null} />);
  fireEvent.click(screen.getByRole("tab", { name: "工作區" }));
  await openBatchMenu("全部停用");
  const confirm = screen.getByRole("button", { name: "確認操作" });
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(batchSkills).toHaveBeenCalledTimes(1);
  expect(batchSkills).toHaveBeenCalledWith("workspace", alphaWorkspace.id, "disable", 1);
  finish?.();
  await screen.findByText("完成 1 個，略過 0 個，失敗 0 個。");
});

it("keeps batch conflicts visible and disables empty-list actions", async () => {
  vi.mocked(batchSkills).mockRejectedValue(new Error("revision_conflict"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await openBatchMenu("全部啟用");
  fireEvent.click(screen.getByRole("button", { name: "確認操作" }));
  expect(await screen.findByText(/revision_conflict/)).toBeTruthy();
  expect(screen.getByRole("dialog")).toBeTruthy();
});

it("disables batch controls for empty scopes", async () => {
  vi.mocked(listSkills).mockResolvedValue({ revision: 0, enabled: true, skills: [] });
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await screen.findByText("尚無 Skills");
  expect((screen.getByRole("button", { name: "批次操作" }) as HTMLButtonElement).disabled).toBe(true);
});

it("shows automatic inheritance read-only and warns about disabled workspace shadowing", async () => {
  const local = { ...skill, id: "44444444-4444-4444-8444-444444444444", scope: "workspace" as const, workspaceId: alphaWorkspace.id };
  vi.mocked(listSkills).mockImplementation(async (scope, workspaceId) => ({ revision: 1, enabled: true,
    skills: scope === "workspace" ? [local] : [{ ...skill, reason: workspaceId ? "shadowed_by_workspace" : "ready", shadowedBySkillId: workspaceId ? local.id : null }] }));
  render(<SkillsSettings workspaces={{ catalog: workspaceCatalog }} container={null} />);
  await screen.findByText("review");
  fireEvent.click(screen.getByRole("tab", { name: "工作區" }));
  expect(await screen.findByText("已由工作區版本取代")).toBeTruthy();
  expect(screen.getByText("繼承自全域")).toBeTruthy();
  expect(screen.getByText("此工作區版本目前不可用，不會回退同名全域版本。")).toBeTruthy();
  expect(screen.getAllByRole("switch")).toHaveLength(2);
  expect(screen.getAllByRole("combobox")).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "移除 review" }));
  expect(await screen.findByText("移除後，後續執行會重新繼承可用的同名全域 Skill。")).toBeTruthy();
  expect(skillRequest).not.toHaveBeenCalled();
});

it.each(["zh-TW", "en", "ja"] as const)("provides inheritance messages in %s", locale => {
  const t = createTranslator(locale);
  for (const key of ["skills.inherited", "skills.inheritanceHint", "skills.shadowed", "skills.nameConflict", "skills.noFallback", "skills.removeInheritance"] as const) {
    expect(t(key)).not.toBe(key);
    expect(t(key).length).toBeGreaterThan(0);
  }
});

it("imports Markdown locally with a filename without saving or enabling", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  fireEvent.click(await screen.findByRole("button", { name: /新增 Skill/ }));
  await screen.findByRole("button", { name: "匯入 SKILL.md" });
  const file = new File([content], "SKILL.md", { type: "text/markdown" });
  Object.defineProperty(file, "arrayBuffer", { value: async () => new TextEncoder().encode(content).buffer });
  fireEvent.change(document.querySelector('input[accept=".md,text/markdown"]')!, { target: { files: [file] } });
  expect((await screen.findByRole("status")).textContent).toBe("SKILL.md");
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(content);
  expect(skillRequest).not.toHaveBeenCalled();
});

it.each([
  ["large.md", "x".repeat(65537), "content_too_large"],
  ["wrong.txt", "text", "invalid_format"],
  ["invalid.md", new Uint8Array([255]), "invalid_format"],
])("rejects invalid import %s without replacing the editor", async (name, bytes, code) => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  fireEvent.click(await screen.findByRole("button", { name: /新增 Skill/ }));
  await screen.findByRole("button", { name: "匯入 SKILL.md" });
  const file = new File([bytes], name);
  Object.defineProperty(file, "arrayBuffer", { value: async () => typeof bytes === "string" ? new TextEncoder().encode(bytes).buffer : bytes.buffer });
  fireEvent.change(document.querySelector('input[accept=".md,text/markdown"]')!, { target: { files: [file] } });
  await waitFor(() => expect(screen.getAllByRole("alert").some(item => item.textContent?.includes(code))).toBe(true));
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("---\nname: \ndescription: \n---\n");
  expect(skillRequest).not.toHaveBeenCalled();
});
it("enables directly without editing or version confirmation", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  const toggle = await screen.findByRole("switch", { name: "啟用 review" });
  fireEvent.click(toggle);
  await waitFor(() => expect(skillRequest).toHaveBeenCalledWith(`/${skill.id}/enabled`, "PUT", { enabled: true, expectedRevision: 1 }));
  expect(screen.queryByRole("button", { name: /編輯|確認此版本/ })).toBeNull();
});
it("shows only the name and icon actions and confirms before removal", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  expect(await screen.findByText("review")).toBeTruthy();
  expect(screen.queryByText("Review")).toBeNull();
  const remove = screen.getByRole("button", { name: "移除 review" });
  expect(remove.textContent).toBe("");
  fireEvent.click(remove);
  expect(skillRequest).not.toHaveBeenCalled();
  fireEvent.click(await screen.findByRole("button", { name: "OK" }));
  await waitFor(() => expect(skillRequest).toHaveBeenCalledWith(`/${skill.id}?expectedRevision=1`, "DELETE", undefined));
});
it("preserves visible settings and reports mutation failure", async () => {
  vi.mocked(skillRequest).mockRejectedValue(new Error("revision_conflict"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await screen.findByText("review");
  fireEvent.click(screen.getAllByRole("switch")[0]);
  expect((await screen.findByRole("alert")).textContent).toContain("revision_conflict");
  expect(screen.getAllByRole("switch")[0].getAttribute("aria-checked")).toBe("true");
});

it("does not expose the previous workspace actions while the next workspace loads", async () => {
  let resolveBeta: ((value: { revision: number; enabled: boolean; skills: typeof skill[] }) => void) | undefined;
  const alphaSkill = { ...skill, id: "44444444-4444-4444-8444-444444444444", scope: "workspace" as const, workspaceId: alphaWorkspace.id, name: "alpha-skill", directoryName: "alpha-skill" };
  vi.mocked(listSkills).mockImplementation(async (scope, workspaceId) => {
    if (scope === "global") return { revision: 1, enabled: true, skills: [] };
    if (workspaceId === alphaWorkspace.id) return { revision: 1, enabled: true, skills: [alphaSkill] };
    return await new Promise(resolve => { resolveBeta = resolve; });
  });
  render(<SkillsSettings workspaces={{ catalog: workspaceCatalog }} container={null} />);
  fireEvent.click(screen.getByRole("tab", { name: "工作區" }));
  expect(await screen.findByText("alpha-skill")).toBeTruthy();

  fireEvent.mouseDown(screen.getByRole("combobox"));
  fireEvent.click(await screen.findByText("Beta"));

  expect(screen.queryByText("alpha-skill")).toBeNull();
  await waitFor(() => expect(resolveBeta).toBeTypeOf("function"));
  resolveBeta?.({ revision: 1, enabled: true, skills: [] });
  await waitFor(() => expect(screen.queryByText("alpha-skill")).toBeNull());
});

it("keeps the editor open when the post-save refresh fails", async () => {
  vi.mocked(listSkills).mockResolvedValueOnce({ revision: 1, enabled: true, skills: [skill] }).mockRejectedValueOnce(new Error("network_error"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  fireEvent.click(await screen.findByRole("button", { name: /新增 Skill/ }));
  fireEvent.click(await screen.findByRole("button", { name: /儲\s*存/ }));

  await waitFor(() => expect(screen.getAllByRole("alert").some(item => item.textContent?.includes("network_error"))).toBe(true));
  expect(screen.getByRole("button", { name: /儲\s*存/ })).toBeTruthy();
  expect((screen.getByRole("textbox") as HTMLTextAreaElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "匯入 SKILL.md" }) as HTMLButtonElement).disabled).toBe(true);
});

it("resets committed state when another folder is selected after closing a failed refresh", async () => {
  vi.mocked(importSkillZip).mockResolvedValue({ revision: 2, skill });
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  const importMenu = await screen.findByRole("button", { name: /匯入 ▾/ });
  await waitFor(() => expect((importMenu as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(importMenu);
  const button = await screen.findByRole("button", { name: "匯入 ZIP" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  const selectFolder = (name: string) => {
    const file = makeZip(name);
    fireEvent.change(document.querySelector('input[accept=".zip,application/zip"]')!, { target: { files: [file] } });
  };
  selectFolder("first");
  const confirm = await screen.findByRole("button", { name: "確認匯入" });
  vi.mocked(listSkills).mockRejectedValueOnce(new Error("network_error"));
  fireEvent.click(confirm);
  await waitFor(() => expect(screen.getAllByRole("alert").some(item => item.textContent?.includes("network_error"))).toBe(true));
  expect((confirm as HTMLButtonElement).disabled).toBe(true);
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("button", { name: "確認匯入" })).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: /重\s*試/ }));
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  selectFolder("second");
  expect((await screen.findByRole("button", { name: "確認匯入" }) as HTMLButtonElement).disabled).toBe(false);
  expect(importSkillZip).toHaveBeenCalledTimes(1);
});

it("keeps save available when the mutation itself fails", async () => {
  vi.mocked(skillRequest).mockRejectedValueOnce(new Error("revision_conflict"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  fireEvent.click(await screen.findByRole("button", { name: /新增 Skill/ }));
  const save = await screen.findByRole("button", { name: /儲\s*存/ });
  fireEvent.click(save);

  await waitFor(() => expect(screen.getAllByRole("alert").some(item => item.textContent?.includes("revision_conflict"))).toBe(true));
  expect((save as HTMLButtonElement).disabled).toBe(false);
});

it("consumes Escape inside the editor and restores its opener", async () => {
  const changed = vi.fn();
  const outer = vi.fn();
  window.addEventListener("keydown", outer);
  try {
    render(<SkillsSettings workspaces={{ catalog: null }} container={null} onOverlayChange={changed} />);
    const edit = await screen.findByRole("button", { name: /新增 Skill/ });
    fireEvent.click(edit);
    await screen.findByRole("button", { name: /儲\s*存/ });
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(changed).toHaveBeenLastCalledWith(false));
    expect(outer).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(edit));
  } finally { window.removeEventListener("keydown", outer); }
});

it("previews a folder and requires explicit confirmation before importing", async () => {
  vi.mocked(importSkillZip).mockResolvedValue({ revision: 2, skill });
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  const importMenu = await screen.findByRole("button", { name: /匯入 ▾/ });
  await waitFor(() => expect((importMenu as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(importMenu);
  const button = await screen.findByRole("button", { name: "匯入 ZIP" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  const file = makeZip("code-review");
  fireEvent.change(document.querySelector('input[accept=".zip,application/zip"]')!, { target: { files: [file] } });
  const confirm = await screen.findByRole("button", { name: "確認匯入" });
  expect(importSkillZip).not.toHaveBeenCalled();
  expect(screen.getByRole("list", { name: "ZIP 檔案清單" }).textContent).toContain("SKILL.md");
  fireEvent.click(confirm);
  await waitFor(() => expect(importSkillZip).toHaveBeenCalledWith("global", null, "code-review", file, 1));
  expect(skillRequest).not.toHaveBeenCalled();
});

it("keeps a failed folder import available for retry and cancels without another write", async () => {
  vi.mocked(importSkillZip).mockRejectedValue(new Error("directory_exists"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  const importMenu = await screen.findByRole("button", { name: /匯入 ▾/ });
  await waitFor(() => expect((importMenu as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(importMenu);
  const button = await screen.findByRole("button", { name: "匯入 ZIP" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  const file = makeZip("code-review");
  fireEvent.change(document.querySelector('input[accept=".zip,application/zip"]')!, { target: { files: [file] } });
  fireEvent.click(await screen.findByRole("button", { name: "確認匯入" }));
  await waitFor(() => expect(screen.getAllByRole("alert").some(item => item.textContent?.includes("directory_exists"))).toBe(true));
  expect(screen.getByRole("list", { name: "ZIP 檔案清單" }).textContent).toContain("SKILL.md");
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(document.activeElement).toBe(button));
  expect(importSkillZip).toHaveBeenCalledTimes(1);
  expect(skillRequest).not.toHaveBeenCalled();
});
function makeZip(name: string) {
  const bytes = zipSync({ [`${name}/SKILL.md`]: new TextEncoder().encode(content) });
  const file = new File([bytes], `${name}.zip`);
  Object.defineProperty(file, "arrayBuffer", { value: async () => bytes.buffer });
  return file;
}
