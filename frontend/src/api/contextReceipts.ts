const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const exact = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).length === keys.length && Object.keys(value).every(key => keys.includes(key));
const integer = (value: unknown, minimum = 0) => Number.isSafeInteger(value) && Number(value) >= minimum;
const hash = (value: unknown) => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
const id = (value: unknown) => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);

export function validContextReceipt(data: unknown): boolean {
  if (!record(data) || !exact(data, ["schemaVersion", "requestHash", "estimateMethod", "estimatedInputTokens", "components", "contextLimitTokens", "inputBudgetTokens", "outputReserveTokens", "messageCount", "toolCount", "systemHash", "toolsHash", "historyMessageIds", "summary", "skills", "workspace"])) return false;
  if (data.schemaVersion !== 1 || data.estimateMethod !== "utf8-conservative-v1" || ![data.requestHash, data.systemHash, data.toolsHash].every(hash)) return false;
  if (![data.estimatedInputTokens, data.messageCount, data.toolCount, data.outputReserveTokens].every(value => integer(value))) return false;
  if (Number(data.messageCount) < 1 || Number(data.messageCount) > 256 || Number(data.outputReserveTokens) < 1 || Number(data.outputReserveTokens) > 131072) return false;
  if (![data.contextLimitTokens, data.inputBudgetTokens].every(value => value === null || integer(value, 1))) return false;
  if (!record(data.components) || !exact(data.components, ["system", "summary", "history", "currentUser", "toolResults", "assistant", "summaryInput", "unattributed", "toolDefinitions", "framing"]) || !Object.values(data.components).every(value => integer(value)) || Object.values(data.components).reduce<number>((sum, value) => sum + Number(value), 0) !== data.estimatedInputTokens) return false;
  if (!Array.isArray(data.historyMessageIds) || data.historyMessageIds.length > 256 || !data.historyMessageIds.every(id) || new Set(data.historyMessageIds).size !== data.historyMessageIds.length) return false;
  if (data.summary !== null && (!record(data.summary) || !exact(data.summary, ["id", "version", "sourceHash", "throughSequence"]) || !id(data.summary.id) || !integer(data.summary.version, 1) || !hash(data.summary.sourceHash) || !integer(data.summary.throughSequence, 1))) return false;
  if (!Array.isArray(data.skills) || data.skills.length > 5 || !data.skills.every(skill => record(skill) && exact(skill, ["id", "revision", "contentHash"]) && id(skill.id) && integer(skill.revision, 1) && hash(skill.contentHash))) return false;
  return data.workspace === null || (record(data.workspace) && exact(data.workspace, ["id", "revision", "mountManifestHash"]) && id(data.workspace.id) && integer(data.workspace.revision, 1) && hash(data.workspace.mountManifestHash));
}
