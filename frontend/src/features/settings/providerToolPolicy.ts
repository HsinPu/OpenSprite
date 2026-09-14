export function normalizeDisabledModels(values: string[]): string[] {
  return [...new Set(values.map(value => value.trim()))];
}

export function disabledModelsError(values: string[]): "models.tools.emptyId" | "models.tools.longId" | "models.tools.tooManyIds" | null {
  if (values.some(value => !value.trim())) return "models.tools.emptyId";
  if (values.some(value => Array.from(value).length > 256)) return "models.tools.longId";
  if (values.length > 1000) return "models.tools.tooManyIds";
  return null;
}
