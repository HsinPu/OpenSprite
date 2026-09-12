"""Validation of content-free context receipts at the persistence boundary."""

import re
from uuid import UUID

_COMPONENTS = {"system", "summary", "history", "currentUser", "toolResults", "assistant", "summaryInput", "unattributed", "toolDefinitions", "framing"}


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**53 - 1


def _hash(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _id(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def valid_context_receipt(data):
    keys = {"schemaVersion", "requestHash", "estimateMethod", "estimatedInputTokens", "components",
            "contextLimitTokens", "inputBudgetTokens", "outputReserveTokens", "messageCount", "toolCount",
            "systemHash", "toolsHash", "historyMessageIds", "summary", "skills", "workspace"}
    if not isinstance(data, dict) or set(data) != keys or type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1:
        return False
    if data["estimateMethod"] != "utf8-conservative-v1" or not all(_hash(data[key]) for key in ("requestHash", "systemHash", "toolsHash")):
        return False
    if not all(_integer(data[key]) for key in ("estimatedInputTokens", "messageCount", "toolCount", "outputReserveTokens")):
        return False
    if not 1 <= data["messageCount"] <= 256 or not 1 <= data["outputReserveTokens"] <= 131072:
        return False
    if not all(data[key] is None or _integer(data[key], 1) for key in ("contextLimitTokens", "inputBudgetTokens")):
        return False
    components = data["components"]
    if not isinstance(components, dict) or set(components) != _COMPONENTS or not all(_integer(value) for value in components.values()) or sum(components.values()) != data["estimatedInputTokens"]:
        return False
    ids = data["historyMessageIds"]
    if not isinstance(ids, list) or len(ids) > 256 or not all(_id(value) for value in ids) or len(set(ids)) != len(ids):
        return False
    summary = data["summary"]
    if summary is not None and (not isinstance(summary, dict) or set(summary) != {"id", "version", "sourceHash", "throughSequence"} or not _id(summary["id"]) or not _integer(summary["version"], 1) or not _hash(summary["sourceHash"]) or not _integer(summary["throughSequence"], 1)):
        return False
    skills = data["skills"]
    if not isinstance(skills, list) or len(skills) > 5 or any(not isinstance(skill, dict) or set(skill) != {"id", "revision", "contentHash"} or not _id(skill["id"]) or not _integer(skill["revision"], 1) or not _hash(skill["contentHash"]) for skill in skills):
        return False
    workspace = data["workspace"]
    return workspace is None or (isinstance(workspace, dict) and set(workspace) == {"id", "revision", "mountManifestHash"} and _id(workspace["id"]) and _integer(workspace["revision"], 1) and _hash(workspace["mountManifestHash"]))
