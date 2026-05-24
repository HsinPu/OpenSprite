function randomToken() {
  return Math.random().toString(36).slice(2, 8);
}

export function generateExternalChatId() {
  return `browser-${Date.now().toString(36)}-${randomToken()}`;
}

export function generateOverlayProfileId() {
  return `profile-${Date.now().toString(36)}-${randomToken()}`;
}

export function externalChatIdFromSessionId(sessionId) {
  const normalized = String(sessionId || "").trim();
  const separatorIndex = normalized.indexOf(":");
  if (separatorIndex < 0) {
    return normalized;
  }
  return normalized.slice(separatorIndex + 1).trim();
}

export function channelFromSessionId(sessionId) {
  const normalized = String(sessionId || "").trim();
  const separatorIndex = normalized.indexOf(":");
  return separatorIndex > 0 ? normalized.slice(0, separatorIndex).trim() : "web";
}

export function isExternalChannelSessionId(value) {
  const normalized = String(value || "").trim();
  return normalized.includes(":") && channelFromSessionId(normalized) !== "web";
}
