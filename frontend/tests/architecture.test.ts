/// <reference types="vite/client" />

import { describe, expect, it } from "vitest";

type Boundary = "api" | "i18n" | "ai-settings" | "chat" | "settings" | "app";

const sourceFiles = import.meta.glob("../src/**/*.{ts,tsx}", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

const allowedDependencies: Record<Boundary, ReadonlySet<Boundary>> = {
  api: new Set(["api", "i18n"]),
  i18n: new Set(["i18n"]),
  "ai-settings": new Set(["ai-settings", "api", "i18n"]),
  chat: new Set(["chat", "ai-settings", "api", "i18n"]),
  settings: new Set(["settings", "ai-settings", "api", "i18n"]),
  app: new Set(["app", "ai-settings", "chat", "settings", "api", "i18n"]),
};

function boundary(path: string): Boundary | null {
  const normalized = path.replaceAll("\\", "/");
  if (normalized.includes("/src/api/")) return "api";
  if (normalized.includes("/src/i18n/")) return "i18n";
  if (normalized.includes("/src/features/ai-settings/")) return "ai-settings";
  if (normalized.includes("/src/features/chat/")) return "chat";
  if (normalized.includes("/src/features/settings/")) return "settings";
  if (normalized.includes("/src/app/")) return "app";
  return null;
}

function resolveRelativeImport(sourcePath: string, specifier: string): string | null {
  if (!specifier.startsWith(".")) return null;
  const segments = sourcePath.replaceAll("\\", "/").split("/");
  segments.pop();
  for (const segment of specifier.split("/")) {
    if (segment === ".") continue;
    if (segment === "..") segments.pop();
    else segments.push(segment);
  }
  return segments.join("/");
}

function relativeImports(source: string): string[] {
  const imports: string[] = [];
  const declaration = /(?:^|\n)\s*(?:import|export)\s+(?:type\s+)?(?:[^"'`;]*?\s+from\s+)?["']([^"']+)["']/g;
  for (const match of source.matchAll(declaration)) imports.push(match[1]);
  return imports;
}

describe("frontend architecture", () => {
  it("keeps source dependencies pointing toward stable boundaries", () => {
    expect(Object.keys(sourceFiles).length).toBeGreaterThan(0);
    const violations: string[] = [];

    for (const [sourcePath, source] of Object.entries(sourceFiles)) {
      const sourceBoundary = boundary(sourcePath);
      if (sourceBoundary === null) continue;
      for (const specifier of relativeImports(source)) {
        const resolved = resolveRelativeImport(sourcePath, specifier);
        if (resolved === null) continue;
        const targetBoundary = boundary(resolved);
        if (targetBoundary !== null && !allowedDependencies[sourceBoundary].has(targetBoundary)) {
          violations.push(`${sourcePath}: ${sourceBoundary} -> ${targetBoundary} (${specifier})`);
        }
      }
    }

    expect(violations).toEqual([]);
  });
});
