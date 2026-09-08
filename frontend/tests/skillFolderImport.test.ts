import { expect, it } from "vitest";
import { inspectSkillFolder } from "../src/features/settings/skillFolderImport";

export const document = "---\nname: review\ndescription: Review code\n---\nCheck it.";
export function file(path: string, content = document) {
  const result = new File([content], path.split("/").at(-1)!);
  Object.defineProperty(result, "webkitRelativePath", { value: path });
  Object.defineProperty(result, "arrayBuffer", { value: async () => new TextEncoder().encode(content).buffer });
  return result;
}
it("previews the whole folder without executing supporting content", async () => {
  const result = await inspectSkillFolder([file("code-review/SKILL.md"), file("code-review/scripts/a.py", "raise RuntimeError")]);
  expect(result.directoryName).toBe("code-review");
  expect(result.name).toBe("review");
  expect(result.files).toHaveLength(2);
});
it.each(["../escape", "x/../y", "x/C:/y", "x/.git/config", "x/nested/SKILL.md", "x/skill.md", "x/NUL", "x/a."])("rejects unsafe structure %s", async path => {
  await expect(inspectSkillFolder([file("x/SKILL.md"), file(path)])).rejects.toThrow();
});
it("rejects duplicate paths, file-directory conflicts and missing entrypoints", async () => {
  for (const paths of [["x/SKILL.md", "x/A", "x/a"], ["x/SKILL.md", "x/a", "x/a/b"], ["x/README.md"]]) {
    await expect(inspectSkillFolder(paths.map(path => file(path)))).rejects.toThrow();
  }
});
it("enforces the portable UTF-8 byte limit for every path segment", async () => {
  const accepted = "😀".repeat(63);
  const rejected = "😀".repeat(64);

  await expect(inspectSkillFolder([file("x/SKILL.md"), file(`x/${accepted}`)])).resolves.toMatchObject({
    files: expect.arrayContaining([expect.objectContaining({ path: accepted })]),
  });
  await expect(inspectSkillFolder([file("x/SKILL.md"), file(`x/${rejected}`)])).rejects.toThrow("unsafe_path");
});
it("accepts a UTF-8 BOM while retaining the original file for upload", async () => {
  const content = `\uFEFF${document}`;
  const skill = file("x/SKILL.md", content);

  const result = await inspectSkillFolder([skill]);

  expect(result.content).toBe(document);
  expect(result.files[0].file).toBe(skill);
});
it("matches the backend policy for contextual Unicode joiners", async () => {
  const emojiJoiner = "developer-👨‍💻.md";
  const languageJoiner = "می‌خواهم.md";

  const result = await inspectSkillFolder([
    file("x/SKILL.md"),
    file(`x/${emojiJoiner}`),
    file(`x/${languageJoiner}`),
  ]);

  expect(result.files.map(item => item.path)).toEqual(["SKILL.md", emojiJoiner, languageJoiner]);
  for (const path of ["‍leading.md", "trailing.md‍", "double‌‍joiner.md"]) {
    await expect(inspectSkillFolder([file("x/SKILL.md"), file(`x/${path}`)])).rejects.toThrow("unsafe_path");
  }
});
it.each([
  "---\nname: x\nname: y\ndescription: z\n---\nBody",
  "---\nname: &n x\ndescription: *n\n---\nBody",
  "---\nname: x\ndescription: z\n---\n",
])("rejects invalid headers", async content => {
  await expect(inspectSkillFolder([file("x/SKILL.md", content)])).rejects.toThrow("invalid_format");
});

it("accepts extra metadata and descriptions longer than 500 characters", async () => {
  const description = "說明".repeat(1000);
  const content = `---\nname: x\ndescription: ${description}\nextra: z\n---\nBody`;
  const result = await inspectSkillFolder([file("x/SKILL.md", content)]);
  expect(result.description).toBe(description);
  expect(result.content).toBe(content);
});
