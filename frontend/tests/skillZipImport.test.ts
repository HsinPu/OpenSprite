import { expect, it } from "vitest";
import { zipSync } from "fflate";
import { inspectSkillZip } from "../src/features/settings/skillZipImport";

const content = new TextEncoder().encode("---\nname: review\ndescription: review code\n---\nReview carefully.");
function zip(entries: Record<string, Uint8Array>, name = "review.zip") {
  const data = zipSync(entries);
  const file = new File([data], name);
  Object.defineProperty(file, "arrayBuffer", { value: async () => data.buffer });
  return file;
}
it("previews wrapped and root ZIPs locally", async () => {
  for (const prefix of ["", "code-review/"]) {
    const archive = zip({ [`${prefix}SKILL.md`]: content });
    const result = await inspectSkillZip(archive);
    expect(result.directoryName).toBe(prefix ? "code-review" : "review");
    expect(result.archive).toBe(archive);
    expect(result.name).toBe("review");
  }
});
it("rejects invalid structure and excessive output", async () => {
  const cases: Record<string, Uint8Array>[] = [
    { "other.md": content },
    { "SKILL.md": content, "../escape": content },
    { "SKILL.md": content, "huge": new Uint8Array(5 * 1024 * 1024 + 1) },
    { "one/SKILL.md": content, "two/SKILL.md": content },
  ];
  for (const entries of cases) await expect(inspectSkillZip(zip(entries))).rejects.toThrow();
});

it.each([
  [".git/SKILL.md"], ["SKILL.md", ".git/"], ["SKILL.md", "../"],
  ["SKILL.md", "assets/", "assets"], ["SKILL.md", "assets", "assets/"],
  ["SKILL.md", "Assets/", "assets/a"], ["SKILL.md", "assets//"],
])("rejects invalid archive nodes %j", async (...paths) => {
  const entries = Object.fromEntries(paths.map(path => [path, path.endsWith("/") ? new Uint8Array() : content]));
  await expect(inspectSkillZip(zip(entries))).rejects.toThrow();
});

it("accepts legitimate empty directories in either entry order", async () => {
  for (const paths of [["review/", "review/assets/", "review/SKILL.md", "review/assets/a"],
    ["review/SKILL.md", "review/assets/a", "review/assets/", "review/"]]) {
    const entries = Object.fromEntries(paths.map(path => [path, path.endsWith("/") ? new Uint8Array() : content]));
    expect((await inspectSkillZip(zip(entries))).files).toHaveLength(2);
  }
});
