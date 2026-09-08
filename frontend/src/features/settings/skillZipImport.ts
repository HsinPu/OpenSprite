import { Unzip, UnzipInflate, unzipSync } from "fflate";
import { inspectSkillFolder, validateArchivePaths, FolderValidationError, type FolderCandidate } from "./skillFolderImport";

export type ZipCandidate = FolderCandidate & { archive: File };
export async function inspectSkillZip(archive: File): Promise<ZipCandidate> {
  if (!archive.name.toLowerCase().endsWith(".zip")) throw new FolderValidationError("invalid_zip");
  if (archive.size > 12 * 1024 * 1024) throw new FolderValidationError("package_too_large");
  try {
    let count = 0, total = 0, fileCount = 0;
    const names = new Set<string>();
    const metadata = new Map<string, number>();
    const bytes = new Uint8Array(await archive.arrayBuffer());
    // Read central-directory limits without decompressing attacker-controlled data.
    unzipSync(bytes, { filter(entry) {
      if (++count > 1800) throw new FolderValidationError("file_count_exceeded");
      if (names.has(entry.name.toLowerCase())) throw new FolderValidationError("duplicate_path");
      names.add(entry.name.toLowerCase());
      metadata.set(entry.name, entry.originalSize);
      if (!entry.name.endsWith("/") && ++fileCount > 200) throw new FolderValidationError("file_count_exceeded");
      total += entry.originalSize;
      if (total > 10 * 1024 * 1024) throw new FolderValidationError("package_too_large");
      if (entry.originalSize > 5 * 1024 * 1024) throw new FolderValidationError("content_too_large");
      return false;
    } });
    validateArchivePaths([...metadata.keys()]);
    const entries = new Map<string, Uint8Array>();
    const started = new Set<string>();
    let expanded = 0;
    const unzip = new Unzip(entry => {
      if (!metadata.has(entry.name) || started.has(entry.name)) throw new FolderValidationError("invalid_zip");
      started.add(entry.name);
      const chunks: Uint8Array[] = [];
      let size = 0;
      entry.ondata = (error, chunk, final) => {
        if (error) throw new FolderValidationError("invalid_zip");
        size += chunk.length; expanded += chunk.length;
        if (expanded > 10 * 1024 * 1024 || size > 5 * 1024 * 1024) throw new FolderValidationError("package_too_large");
        chunks.push(chunk);
        if (final) {
          if (size !== metadata.get(entry.name)) throw new FolderValidationError("invalid_zip");
          if (!entry.name.endsWith("/")) {
            const data = new Uint8Array(size);
            let offset = 0;
            for (const part of chunks) { data.set(part, offset); offset += part.length; }
            entries.set(entry.name, data);
          }
        }
      };
      entry.start();
    });
    unzip.register(UnzipInflate);
    // Bound actual expansion, not only the ZIP's claimed uncompressed sizes.
    for (let offset = 0; offset < bytes.length; offset += 256) {
      unzip.push(bytes.subarray(offset, offset + 256), offset + 256 >= bytes.length);
      if (offset && offset % 131072 === 0) await new Promise(resolve => setTimeout(resolve, 0));
    }
    if (started.size !== metadata.size) throw new FolderValidationError("invalid_zip");
    const paths = [...entries.keys()];
    if (paths.length !== fileCount) throw new FolderValidationError("invalid_zip");
    if (!paths.length) throw new FolderValidationError("missing_entrypoint");
    const wrapped = !paths.includes("SKILL.md");
    const directoryName = wrapped ? paths[0].split("/")[0] : archive.name.slice(0, -4);
    const files = paths.map(path => {
      const data = new Uint8Array(entries.get(path)!);
      const file = new File([data], path.split("/").at(-1) ?? path);
      Object.defineProperty(file, "arrayBuffer", { value: async () => data.buffer });
      Object.defineProperty(file, "webkitRelativePath", { value: wrapped ? path : `${directoryName}/${path}` });
      return file;
    });
    return { ...await inspectSkillFolder(files), archive };
  } catch (error) {
    if (error instanceof FolderValidationError) throw error;
    throw new FolderValidationError("invalid_zip");
  }
}
