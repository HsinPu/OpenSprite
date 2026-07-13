export const LANGUAGE_OPTIONS = ["zh-TW", "en"] as const;
export type LanguagePreference = (typeof LANGUAGE_OPTIONS)[number];
export const DEFAULT_LANGUAGE: LanguagePreference = "zh-TW";
export const SUPPORTED_LANGUAGES: ReadonlySet<LanguagePreference> = new Set(LANGUAGE_OPTIONS);

export const COLOR_SCHEME_OPTIONS = ["system", "light", "dark"] as const;
export type ColorSchemePreference = (typeof COLOR_SCHEME_OPTIONS)[number];
export type ResolvedColorScheme = Exclude<ColorSchemePreference, "system">;
export const DEFAULT_COLOR_SCHEME: ColorSchemePreference = "system";
export const SUPPORTED_COLOR_SCHEMES: ReadonlySet<ColorSchemePreference> = new Set(COLOR_SCHEME_OPTIONS);

export function readStoredValue(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function isAllowedChoice<T extends string>(value: string, allowedValues: ReadonlySet<T>): value is T {
  for (const allowedValue of allowedValues) {
    if (allowedValue === value) {
      return true;
    }
  }
  return false;
}

export function normalizeChoice<T extends string>(value: unknown, fallback: T, allowedValues: ReadonlySet<T>): T {
  const normalized = String(value || "").trim();
  return isAllowedChoice(normalized, allowedValues) ? normalized : fallback;
}

export function readStoredChoice<T extends string>(key: string, fallback: T, allowedValues: ReadonlySet<T>): T {
  return normalizeChoice(readStoredValue(key, fallback), fallback, allowedValues);
}

export function getResolvedColorScheme(colorScheme: ColorSchemePreference): ResolvedColorScheme {
  if (colorScheme !== "system") {
    return colorScheme;
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function writeStoredValue(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    return;
  }
}

export function readStoredBoolean(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key);
    if (value === null) {
      return fallback;
    }
    return value === "true";
  } catch {
    return fallback;
  }
}
