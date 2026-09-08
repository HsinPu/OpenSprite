import { parseDocument, visit } from "yaml";

export type FolderCandidate = {
  directoryName: string; name: string; description: string; content: string;
  files: { path: string; file: File }[]; totalBytes: number;
};
export class FolderValidationError extends Error {
  constructor(readonly code: string, readonly path?: string) { super(code); }
}
const excluded = new Set([".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__"]);
const maxPortableSegmentUtf8Bytes = 255;
const safeNameFormatCharacters = new Set(["\u200c", "\u200d"]);
const utf8Encoder = new TextEncoder();
function hasUnsafeNameControls(value: string): boolean {
  const characters = [...value];
  return characters.some((character, index) => {
    if (/[\p{Cc}\p{Cs}]/u.test(character)) return true;
    if (!/\p{Cf}/u.test(character)) return false;
    if (!safeNameFormatCharacters.has(character) || index === 0 || index === characters.length - 1) return true;
    return safeNameFormatCharacters.has(characters[index - 1]) || safeNameFormatCharacters.has(characters[index + 1]);
  });
}
function segment(value: string): string {
  if (!value || [...value].length > 80 || utf8Encoder.encode(value).byteLength > maxPortableSegmentUtf8Bytes
    || value !== value.trim() || value !== value.normalize("NFC")
    || /[<>:"/\\|?*]/u.test(value) || hasUnsafeNameControls(value) || /[. ]$/.test(value)
    || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(value)) throw new FolderValidationError("unsafe_path");
  return value;
}
export function validateArchivePaths(paths: string[]): void {
  const nodes = new Map<string, { path: string; file: boolean }>();
  const explicit = new Set<string>();
  for (const path of paths) {
    const directory = path.endsWith("/");
    const parts = (directory ? path.slice(0, -1) : path).split("/");
    if (parts.length > 9) throw new FolderValidationError("directory_depth_exceeded");
    parts.forEach(segment);
    if (parts.some(part => excluded.has(part.toLowerCase()))) throw new FolderValidationError("excluded_directory");
    const key = parts.join("/").toLowerCase();
    if (explicit.has(key)) throw new FolderValidationError("duplicate_path");
    explicit.add(key);
    for (let index = 1; index <= parts.length; index++) {
      const prefix = parts.slice(0, index).join("/");
      const file = index === parts.length && !directory;
      const previous = nodes.get(prefix.toLowerCase());
      if (previous && (previous.path !== prefix || previous.file || file)) throw new FolderValidationError("duplicate_path");
      nodes.set(prefix.toLowerCase(), { path: prefix, file });
    }
  }
}

export async function inspectSkillFolder(files: File[]): Promise<FolderCandidate> {
  if (!files.length || files.length > 200) throw new FolderValidationError("file_count_exceeded");
  const root = segment(files[0].webkitRelativePath.split("/")[0]);
  if (excluded.has(root.toLowerCase())) throw new FolderValidationError("excluded_directory", root);
  const nodes = new Map<string, { path: string; file: boolean }>();
  let totalBytes = 0;
  const entries = files.map(file => {
    const parts = file.webkitRelativePath.split("/");
    if (parts.shift() !== root || !parts.length) throw new FolderValidationError("unsafe_path");
    if (parts.length > 8) throw new FolderValidationError("directory_depth_exceeded");
    parts.forEach(segment);
    const path = parts.join("/");
    if (parts.some(part => excluded.has(part.toLowerCase()))) throw new FolderValidationError("excluded_directory", path);
    if (parts.at(-1)?.toLowerCase() === "skill.md" && path !== "SKILL.md") throw new FolderValidationError("invalid_entrypoint", path);
    for (let index = 1; index <= parts.length; index++) {
      const prefix = parts.slice(0, index).join("/");
      const key = prefix.toLowerCase();
      const isFile = index === parts.length;
      const previous = nodes.get(key);
      if (previous && (previous.path !== prefix || previous.file || isFile)) throw new FolderValidationError("duplicate_path", path);
      nodes.set(key, { path: prefix, file: isFile });
    }
    if (file.size > (path === "SKILL.md" ? 65536 : 5 * 1024 * 1024)) throw new FolderValidationError("content_too_large", path);
    totalBytes += file.size;
    if (totalBytes > 10 * 1024 * 1024) throw new FolderValidationError("package_too_large");
    return { path, file };
  });
  const entry = entries.find(item => item.path === "SKILL.md");
  if (!entry) throw new FolderValidationError("missing_entrypoint");
  try {
    const content = new TextDecoder("utf-8", { fatal: true }).decode(await entry.file.arrayBuffer());
    const lines = content.split(/\r?\n/);
    const end = lines.indexOf("---", 1);
    if (lines[0] !== "---" || end < 1 || !lines.slice(end + 1).join("\n").trim()) throw new Error();
    const document = parseDocument(lines.slice(1, end).join("\n"), { version: "1.1", uniqueKeys: true, prettyErrors: false });
    if (document.errors.length || document.warnings.length) throw new Error();
    visit(document, { Alias() { throw new Error(); } });
    const header: unknown = document.toJS({ maxAliasCount: 0 });
    if (!header || typeof header !== "object" || Array.isArray(header)) throw new Error();
    const record = header as Record<string, unknown>;
    if (typeof record.name !== "string" || typeof record.description !== "string") throw new Error();
    const name = record.name.normalize("NFC").trim(), description = record.description.trim();
    if (!name || [...name].length > 80 || /[\p{Cc}\p{Cs}]/u.test(name) || !description) throw new Error();
    return { directoryName: root, name, description, content, files: entries, totalBytes };
  } catch { throw new FolderValidationError("invalid_format", "SKILL.md"); }
}
