export function coerceBoolean(value) {
  return value === true || value === "true" || value === 1;
}

export function coerceStringList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}
