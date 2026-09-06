import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { SkillsSettings } from "../src/features/settings/SkillsSettings";
import { getSkill, listSkills, skillRequest } from "../src/api/skills";

vi.mock("../src/api/skills", async importOriginal => ({ ...await importOriginal<typeof import("../src/api/skills")>(), getSkill: vi.fn(), listSkills: vi.fn(), skillRequest: vi.fn() }));
const content = "---\nname: review\ndescription: Review\n---\nCheck it.";
const skill = { id: "11111111-1111-4111-8111-111111111111", scope: "global" as const, workspaceId: null,
  name: "review", description: "Review", directoryName: "review", revision: 1, enabled: false,
  confirmedHash: null, disabledWorkspaces: [], contentHash: "a".repeat(64), state: "pending", effective: false, reason: "pending", content };
beforeEach(() => {
  vi.mocked(listSkills).mockResolvedValue({ revision: 1, enabled: true, skills: [skill] });
  vi.mocked(getSkill).mockResolvedValue({ revision: 1, skill });
  vi.mocked(skillRequest).mockResolvedValue({ revision: 2, enabled: true });
});
it("requires preview confirmation to enable a version", async () => {
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  fireEvent.click(await screen.findByRole("button", { name: /編\s*輯/ }));
  fireEvent.click(await screen.findByRole("button", { name: "確認此版本並啟用" }));
  await waitFor(() => expect(skillRequest).toHaveBeenCalledWith(`/${skill.id}/enabled`, "PUT", { enabled: true, confirmedHash: skill.contentHash, expectedRevision: 1 }));
});
it("preserves visible settings and reports mutation failure", async () => {
  vi.mocked(skillRequest).mockRejectedValue(new Error("revision_conflict"));
  render(<SkillsSettings workspaces={{ catalog: null }} container={null} />);
  await screen.findByText("review");
  fireEvent.click(screen.getByRole("switch"));
  expect((await screen.findByRole("alert")).textContent).toContain("revision_conflict");
  expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");
});

it("consumes Escape inside the editor and restores its opener", async () => {
  const changed = vi.fn();
  const outer = vi.fn();
  window.addEventListener("keydown", outer);
  try {
    render(<SkillsSettings workspaces={{ catalog: null }} container={null} onOverlayChange={changed} />);
    const edit = await screen.findByRole("button", { name: /編\s*輯/ });
    fireEvent.click(edit);
    await screen.findByRole("button", { name: "確認此版本並啟用" });
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(changed).toHaveBeenLastCalledWith(false));
    expect(outer).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(edit));
  } finally { window.removeEventListener("keydown", outer); }
});
