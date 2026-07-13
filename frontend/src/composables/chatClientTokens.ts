export function randomToken(): string {
  return Math.random().toString(36).slice(2, 8);
}
