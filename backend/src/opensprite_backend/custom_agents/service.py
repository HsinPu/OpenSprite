"""Management and immutable-snapshot service for custom Agent definitions.

This module intentionally owns only local catalog/file management.  HTTP
routes, the Agent loop, and the Workspace mutation gate remain separate
boundaries.  Callers that mutate the catalog must serialize those calls with
the Workspace gate before using this service's internal RLock.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from opensprite_backend.app_paths import AppPaths
from opensprite_backend.atomic_file import atomic_write
from opensprite_backend.workspaces import WorkspaceAvailability, WorkspaceRootPolicy
from opensprite_backend.workspaces.relocation import (
    WorkspaceRelocationError,
    ensure_plain_directory,
    require_plain_directory,
)

from .definition import AgentDefinitionError, parse_agent_definition
from .models import (
    AgentCandidate,
    AgentCatalog,
    AgentError,
    AgentExecutionSnapshot,
    AgentRecord,
)
from .policy import execution_snapshot, resolve_agents
from .store import AgentCatalogStore, require_safe_file


_MAX_DEFINITION_BYTES = 64 * 1024
_MAX_PAGE_SIZE = 1000
_JOURNAL_VERSION = 1
_ALLOWED_ACTIONS = frozenset({"write", "archive"})
_ERRORS_TO_INVALID_FORMAT = frozenset(
    {
        "invalid_content",
        "invalid_utf8",
        "invalid_name",
        "invalid_description",
        "invalid_developer_instructions",
        "invalid_provider_id",
        "invalid_model",
        "provider_model_pair_required",
        "unknown_field",
        "duplicate_field",
        "missing_field",
        "invalid_format",
    }
)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


class CustomAgentsService:
    """Thread-safe catalog and file operations for global/workspace Agents."""

    def __init__(self, paths: AppPaths, workspaces) -> None:
        self.paths = paths
        self.workspaces = workspaces
        self.store = AgentCatalogStore(paths)
        self.lock = RLock()

    # ----- catalog and transaction boundary ---------------------------------

    def _catalog(self) -> AgentCatalog:
        self._recover()
        return self.store.read()

    def _recover(self) -> None:
        journal = self.paths.agents_transaction_file
        try:
            require_safe_file(journal, allow_missing=True)
            if not journal.exists():
                return
            with journal.open("rb") as stream:
                payload = stream.read(32 * 1024 * 1024 + 1)
            if len(payload) > 32 * 1024 * 1024:
                raise ValueError
            raw = json.loads(payload, object_pairs_hook=_unique_object)
            if (
                type(raw) is not dict
                or set(raw) != {"version", "catalog", "actions"}
                or raw["version"] != _JOURNAL_VERSION
                or type(raw["actions"]) is not list
            ):
                raise ValueError
            # The journal is parsed as plain JSON first so duplicate keys are
            # rejected.  Re-encode that validated object before Pydantic
            # validation because strict tuple fields do not accept a mutable
            # JSON list through ``model_validate``.
            catalog = AgentCatalog.model_validate_json(_json_bytes(raw["catalog"]))
            actions = self._validate_actions(raw["actions"])
            self._apply_actions(actions)
            self.store.write(catalog)
            self._remove_journal()
        except AgentError:
            raise AgentError("store_unavailable") from None
        except Exception:
            raise AgentError("store_unavailable") from None

    def _commit(self, catalog: AgentCatalog, actions: list[dict[str, object]]) -> None:
        """Write a recoverable journal, apply files, then replace the catalog."""

        try:
            validated_actions = self._validate_actions(actions)
            journal = self.paths.agents_transaction_file
            require_safe_file(journal, allow_missing=True)
            payload = {
                "version": _JOURNAL_VERSION,
                "catalog": catalog.model_dump(mode="json"),
                "actions": validated_actions,
            }
            if len(_json_bytes(payload)) > 32 * 1024 * 1024:
                raise ValueError
            atomic_write(journal, _json_bytes(payload))
            self._apply_actions(validated_actions)
            self.store.write(catalog)
            self._remove_journal()
        except AgentError:
            raise AgentError("store_unavailable") from None
        except Exception:
            raise AgentError("store_unavailable") from None

    def _remove_journal(self) -> None:
        journal = self.paths.agents_transaction_file
        require_safe_file(journal, allow_missing=True)
        if journal.exists():
            journal.unlink()

    @staticmethod
    def _validate_actions(actions: object) -> list[dict[str, object]]:
        if type(actions) is not list:
            raise ValueError
        validated: list[dict[str, object]] = []
        for action in actions:
            if type(action) is not dict or "action" not in action:
                raise ValueError
            kind = action.get("action")
            if kind == "write":
                if set(action) != {"action", "record", "content"}:
                    raise ValueError
                if type(action["content"]) is not str:
                    raise ValueError
                try:
                    raw = base64.b64decode(action["content"], validate=True)
                except Exception:
                    raise ValueError from None
                if len(raw) > _MAX_DEFINITION_BYTES:
                    raise ValueError
                record = AgentRecord.model_validate(action["record"])
                validated.append(
                    {
                        "action": "write",
                        "record": record.model_dump(mode="json"),
                        "content": action["content"],
                    }
                )
            elif kind == "archive":
                if set(action) != {"action", "record", "archiveId"}:
                    raise ValueError
                record = AgentRecord.model_validate(action["record"])
                archive_id = action["archiveId"]
                try:
                    parsed = UUID(archive_id)
                except (TypeError, ValueError, AttributeError):
                    raise ValueError from None
                if str(parsed) != archive_id:
                    raise ValueError
                validated.append(
                    {
                        "action": "archive",
                        "record": record.model_dump(mode="json"),
                        "archiveId": archive_id,
                    }
                )
            else:
                raise ValueError
        return validated

    def _apply_actions(self, actions: list[dict[str, object]]) -> None:
        for action in actions:
            record = AgentRecord.model_validate(action["record"])
            if action["action"] == "write":
                raw = base64.b64decode(action["content"], validate=True)
                path = self._record_path(record, allow_missing=True)
                try:
                    ensure_plain_directory(path.parent)
                except (OSError, WorkspaceRelocationError):
                    raise AgentError("unsafe_path") from None
                atomic_write(path, raw)
                continue
            try:
                source = self._record_path(record, allow_missing=True)
            except AgentError as error:
                if error.code == "workspace_unavailable":
                    # Removing a registration must remain possible while its
                    # workspace is offline; leave the physical file in place.
                    continue
                raise
            archive = self._archive_path(record, str(action["archiveId"]))
            require_safe_file(archive, allow_missing=True)
            try:
                ensure_plain_directory(archive.parent)
            except (OSError, WorkspaceRelocationError):
                raise AgentError("unsafe_path") from None
            if archive.exists():
                require_plain_directory(archive.parent)
                if source.exists():
                    raise ValueError
                continue
            if not source.exists():
                # A removed or already externally-deleted file does not make
                # catalog removal unsafe; the physical data is preserved when
                # it still exists.
                continue
            require_plain_directory(source.parent)
            require_plain_directory(archive.parent)
            source.rename(archive)

    # ----- path and content helpers -----------------------------------------

    @staticmethod
    def _validate_scope(scope: str, workspace_id: str | None) -> None:
        if scope == "global":
            if workspace_id is not None:
                raise AgentError("invalid_request")
            return
        if scope != "workspace" or type(workspace_id) is not str:
            raise AgentError("invalid_request")
        try:
            UUID(workspace_id)
        except (TypeError, ValueError, AttributeError):
            raise AgentError("invalid_request") from None

    def _workspace_context(self, workspace_id: str) -> object:
        try:
            return self.workspaces.execution_context(workspace_id)
        except Exception:
            raise AgentError("workspace_unavailable") from None

    def _base_for_record(self, record: AgentRecord) -> Path:
        if record.scope == "global":
            return self.paths.agents_dir
        context = self._workspace_context(record.workspaceId or "")
        if (
            context.availability is not WorkspaceAvailability.AVAILABLE
            or context.root_path is None
        ):
            raise AgentError("workspace_unavailable")
        return self.paths.workspace_agents_dir(Path(context.root_path))

    def _record_path(self, record: AgentRecord, *, allow_missing: bool) -> Path:
        try:
            WorkspaceRootPolicy.persisted_directory_name(record.fileName)
        except ValueError:
            raise AgentError("unsafe_path") from None
        path = self._base_for_record(record) / record.fileName
        require_safe_file(path, allow_missing=allow_missing)
        return path

    def _archive_path(self, record: AgentRecord, archive_id: str) -> Path:
        try:
            WorkspaceRootPolicy.persisted_directory_name(record.fileName)
            UUID(archive_id)
        except (TypeError, ValueError, AttributeError):
            raise AgentError("unsafe_path") from None
        path = self.paths.agents_archive_dir / archive_id / record.fileName
        require_safe_file(path, allow_missing=True)
        return path

    def _read_bytes(self, record: AgentRecord) -> bytes:
        path = self._record_path(record, allow_missing=False)
        try:
            with path.open("rb") as stream:
                payload = stream.read(_MAX_DEFINITION_BYTES + 1)
        except AgentError:
            raise
        except FileNotFoundError:
            raise AgentError("missing") from None
        except (OSError, ValueError, RuntimeError):
            raise AgentError("unsafe_path") from None
        if len(payload) > _MAX_DEFINITION_BYTES:
            raise AgentError("content_too_large")
        return payload

    @staticmethod
    def _parse_content(content: str):
        if type(content) is not str:
            raise AgentError("invalid_request")
        try:
            raw = content.encode("utf-8")
        except UnicodeError:
            raise AgentError("invalid_format") from None
        try:
            return raw, parse_agent_definition(raw)
        except AgentDefinitionError as error:
            code = error.code
            if code == "content_too_large":
                raise AgentError(code) from None
            raise AgentError("invalid_format") from None
        except (UnicodeError, ValueError):
            raise AgentError("invalid_format") from None

    def _load_candidate(
        self, record: AgentRecord, *, context: object | None = None
    ) -> tuple[AgentCandidate, bytes | None]:
        if record.scope == "workspace":
            if context is None or (
                context.availability is not WorkspaceAvailability.AVAILABLE
                or context.root_path is None
            ):
                return AgentCandidate(record, None, "workspace_unavailable"), None
        try:
            raw = self._read_bytes(record)
            definition = parse_agent_definition(raw)
            return AgentCandidate(record, definition, None), raw
        except AgentDefinitionError as error:
            code = (
                "content_too_large"
                if error.code == "content_too_large"
                else "invalid_format"
            )
            return AgentCandidate(record, None, code), None
        except AgentError as error:
            return AgentCandidate(record, None, error.code), None
        except (OSError, UnicodeError, ValueError, RuntimeError):
            return AgentCandidate(record, None, "unsafe_path"), None

    @staticmethod
    def _name_key(candidate: AgentCandidate) -> str:
        return candidate.name_key

    def _candidate_names(
        self, records: tuple[AgentRecord, ...], workspace_id: str | None = None
    ) -> tuple[AgentCandidate, ...]:
        context = None
        if workspace_id is not None:
            context = self._workspace_context(workspace_id)
        result: list[AgentCandidate] = []
        for record in records:
            if record.scope == "global" or record.workspaceId == workspace_id:
                candidate, _ = self._load_candidate(record, context=context)
                result.append(candidate)
        return tuple(result)

    def _decisions(
        self,
        catalog: AgentCatalog,
        workspace_id: str | None,
        scope: str,
    ) -> tuple[tuple[AgentCandidate, ...], tuple[object, ...]]:
        if scope == "global":
            records = tuple(item for item in catalog.agents if item.scope == "global")
            policy_workspace = workspace_id or "00000000-0000-4000-8000-000000000000"
        else:
            records = tuple(
                item
                for item in catalog.agents
                if item.scope == "global" or item.workspaceId == workspace_id
            )
            policy_workspace = workspace_id or ""
        candidates = self._candidate_names(records, workspace_id if scope == "workspace" else None)
        decisions = resolve_agents(candidates, policy_workspace, enabled=catalog.enabled)
        return candidates, decisions

    @staticmethod
    def _normalise_reason(reason: str) -> str:
        return reason if reason in {"effective", "disabled", "master_disabled", "shadowed_by_workspace", "duplicate_name", "missing", "invalid_format", "content_too_large", "unsafe_path", "workspace_unavailable"} else "invalid_format"

    @classmethod
    def _item(
        cls,
        decision,
        *,
        content: bytes | None = None,
        include_content: bool = False,
    ) -> dict[str, object]:
        candidate = decision.candidate
        record = candidate.record
        definition = candidate.definition
        result: dict[str, object] = {
            "id": record.id,
            "scope": record.scope,
            "workspaceId": record.workspaceId,
            "fileName": record.fileName,
            "name": definition.name if definition is not None else record.name,
            "description": definition.description if definition is not None else "",
            "revision": record.revision,
            "enabled": record.enabled,
            "reason": cls._normalise_reason(decision.reason),
            "shadowedByAgentId": decision.shadowed_by,
            "providerId": definition.provider_id if definition is not None else None,
            "model": definition.model if definition is not None else None,
            "contentHash": definition.content_hash if definition is not None else None,
        }
        if include_content and content is not None:
            try:
                result["content"] = content.decode("utf-8")
            except UnicodeDecodeError:
                result["content"] = None
        elif include_content:
            result["content"] = None
        return result

    @staticmethod
    def _expected(catalog: AgentCatalog, expected_revision: int) -> None:
        if type(expected_revision) is not int or expected_revision < 0:
            raise AgentError("invalid_request")
        if catalog.revision != expected_revision:
            raise AgentError("revision_conflict")

    @staticmethod
    def _find(catalog: AgentCatalog, identifier: str) -> AgentRecord:
        if type(identifier) is not str:
            raise AgentError("invalid_request")
        try:
            UUID(identifier)
        except (TypeError, ValueError, AttributeError):
            raise AgentError("invalid_request") from None
        item = next((item for item in catalog.agents if item.id == identifier), None)
        if item is None:
            raise AgentError("not_found")
        return item

    @staticmethod
    def _encode_cursor(identifier: str) -> str:
        return base64.urlsafe_b64encode(
            json.dumps([identifier], separators=(",", ":")).encode("ascii")
        ).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(value: str) -> str:
        if type(value) is not str or not value:
            raise AgentError("invalid_request")
        try:
            padded = value + "=" * (-len(value) % 4)
            raw = json.loads(base64.urlsafe_b64decode(padded).decode("ascii"))
            if type(raw) is not list or len(raw) != 1 or type(raw[0]) is not str:
                raise ValueError
            UUID(raw[0])
            return raw[0]
        except Exception:
            raise AgentError("invalid_request") from None

    # ----- public catalog operations ----------------------------------------

    def settings(self) -> dict[str, object]:
        with self.lock:
            catalog = self._catalog()
            return {"enabled": catalog.enabled, "revision": catalog.revision}

    def set_settings(self, enabled: bool, expected_revision: int) -> dict[str, object]:
        if type(enabled) is not bool:
            raise AgentError("invalid_request")
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            updated = catalog.model_copy(
                update={"enabled": enabled, "revision": catalog.revision + 1}
            )
            self._commit(updated, [])
            return {"enabled": updated.enabled, "revision": updated.revision}

    def list_agents(
        self,
        scope: str,
        workspace_id: str | None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        self._validate_scope(scope, workspace_id)
        if type(limit) is not int or isinstance(limit, bool) or not 1 <= limit <= _MAX_PAGE_SIZE:
            raise AgentError("invalid_request")
        with self.lock:
            catalog = self._catalog()
            _, decisions = self._decisions(catalog, workspace_id, scope)
            if scope == "global":
                visible = list(decisions)
            else:
                visible = list(decisions)
            start = 0
            if cursor is not None:
                after = self._decode_cursor(cursor)
                indices = [index for index, item in enumerate(visible) if item.candidate.record.id == after]
                if not indices:
                    raise AgentError("invalid_request")
                start = indices[0] + 1
            page = visible[start : start + limit]
            next_cursor = None
            if start + limit < len(visible):
                next_cursor = self._encode_cursor(page[-1].candidate.record.id)
            return {
                "revision": catalog.revision,
                "items": [self._item(item) for item in page],
                "nextCursor": next_cursor,
            }

    def get(self, identifier: str) -> dict[str, object]:
        with self.lock:
            catalog = self._catalog()
            record = self._find(catalog, identifier)
            workspace_id = record.workspaceId if record.scope == "workspace" else None
            scope = "workspace" if record.scope == "workspace" else "global"
            candidates, decisions = self._decisions(catalog, workspace_id, scope)
            decision = next(
                (item for item in decisions if item.candidate.record.id == record.id),
                None,
            )
            if decision is None:
                raise AgentError("not_found")
            _, raw = self._load_candidate(
                record,
                context=(self._workspace_context(workspace_id) if workspace_id else None),
            )
            return self._item(decision, content=raw, include_content=True)

    def create(
        self,
        scope: str,
        workspace_id: str | None,
        content: str,
        expected_revision: int,
    ) -> dict[str, object]:
        self._validate_scope(scope, workspace_id)
        raw, definition = self._parse_content(content)
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            if scope == "workspace":
                context = self._workspace_context(workspace_id or "")
                if context.availability is not WorkspaceAvailability.AVAILABLE or context.root_path is None:
                    raise AgentError("workspace_unavailable")
            peers = tuple(
                item
                for item in catalog.agents
                if item.scope == scope and item.workspaceId == workspace_id
            )
            if self._has_duplicate_name(
                peers, definition.name.casefold(), workspace_id=workspace_id
            ):
                raise AgentError("duplicate_name")
            identifier = str(uuid4())
            file_name = f"agent-{identifier}.toml"
            record = AgentRecord(
                id=identifier,
                scope=scope,
                workspaceId=workspace_id,
                fileName=file_name,
                name=definition.name,
                revision=1,
                enabled=True,
            )
            self._record_path(record, allow_missing=True)
            updated = catalog.model_copy(
                update={
                    "revision": catalog.revision + 1,
                    "agents": (*catalog.agents, record),
                }
            )
            self._commit(updated, [self._write_action(record, raw)])
            item = self.get(identifier)
            item.pop("content", None)
            return item

    def update(
        self, identifier: str, content: str, expected_revision: int
    ) -> dict[str, object]:
        raw, definition = self._parse_content(content)
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            current = self._find(catalog, identifier)
            if current.scope == "workspace":
                context = self._workspace_context(current.workspaceId or "")
                if context.availability is not WorkspaceAvailability.AVAILABLE or context.root_path is None:
                    raise AgentError("workspace_unavailable")
            peers = tuple(
                item
                for item in catalog.agents
                if item.scope == current.scope
                and item.workspaceId == current.workspaceId
                and item.id != current.id
            )
            if self._has_duplicate_name(
                peers, definition.name.casefold(), workspace_id=current.workspaceId
            ):
                raise AgentError("duplicate_name")
            updated_record = current.model_copy(
                update={"name": definition.name, "revision": current.revision + 1}
            )
            updated = catalog.model_copy(
                update={
                    "revision": catalog.revision + 1,
                    "agents": tuple(
                        updated_record if item.id == current.id else item
                        for item in catalog.agents
                    ),
                }
            )
            self._commit(updated, [self._write_action(updated_record, raw)])
            item = self.get(identifier)
            item.pop("content", None)
            return item

    def set_enabled(
        self, identifier: str, enabled: bool, expected_revision: int
    ) -> dict[str, object]:
        if type(enabled) is not bool:
            raise AgentError("invalid_request")
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            current = self._find(catalog, identifier)
            updated_record = current.model_copy(
                update={"enabled": enabled, "revision": current.revision + 1}
            )
            updated = catalog.model_copy(
                update={
                    "revision": catalog.revision + 1,
                    "agents": tuple(
                        updated_record if item.id == current.id else item
                        for item in catalog.agents
                    ),
                }
            )
            self._commit(updated, [])
            item = self.get(identifier)
            item.pop("content", None)
            return item

    def remove(self, identifier: str, expected_revision: int) -> None:
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            current = self._find(catalog, identifier)
            updated = catalog.model_copy(
                update={
                    "revision": catalog.revision + 1,
                    "agents": tuple(item for item in catalog.agents if item.id != identifier),
                }
            )
            self._commit(updated, [self._archive_action(current)])

    def scan(
        self, scope: str, workspace_id: str | None, expected_revision: int
    ) -> dict[str, object]:
        self._validate_scope(scope, workspace_id)
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            base = self._scan_base(scope, workspace_id)
            if not base.exists():
                # A missing directory is a valid empty catalog, but a broken
                # link or non-directory at that location must still fail
                # closed instead of being treated as an empty scan.
                require_safe_file(base / ".scan-probe", allow_missing=True)
                return {"added": 0, "revision": catalog.revision}
            try:
                require_plain_directory(base)
                existing = {
                    item.fileName.casefold()
                    for item in catalog.agents
                    if item.scope == scope and item.workspaceId == workspace_id
                }
                context = self._workspace_context(workspace_id or "") if scope == "workspace" else None
                names = {
                    self._load_candidate(item, context=context)[0].name_key
                    for item in catalog.agents
                    if item.scope == scope and item.workspaceId == workspace_id
                }
                additions: list[AgentRecord] = []
                for child in sorted(base.iterdir(), key=lambda path: path.name.casefold()):
                    if not child.is_file() or not child.name.casefold().endswith(".toml"):
                        continue
                    if child.name.casefold() in existing:
                        continue
                    try:
                        require_safe_file(child)
                        with child.open("rb") as stream:
                            raw = stream.read(_MAX_DEFINITION_BYTES + 1)
                        if len(raw) > _MAX_DEFINITION_BYTES:
                            continue
                        definition = parse_agent_definition(raw)
                        if definition.name_key in names:
                            continue
                        record = AgentRecord(
                            id=str(uuid4()),
                            scope=scope,
                            workspaceId=workspace_id,
                            fileName=child.name,
                            name=definition.name,
                            revision=1,
                            enabled=True,
                        )
                    except (
                        AgentDefinitionError,
                        AgentError,
                        OSError,
                        ValueError,
                        RuntimeError,
                        WorkspaceRelocationError,
                    ):
                        continue
                    additions.append(record)
                    existing.add(child.name.casefold())
                    names.add(definition.name_key)
                if not additions:
                    return {"added": 0, "revision": catalog.revision}
                updated = catalog.model_copy(
                    update={
                        "revision": catalog.revision + 1,
                        "agents": (*catalog.agents, *additions),
                    }
                )
                self._commit(updated, [])
                return {"added": len(additions), "revision": updated.revision}
            except AgentError:
                raise
            except (OSError, ValueError, RuntimeError, WorkspaceRelocationError):
                raise AgentError("unsafe_path") from None

    def batch(
        self,
        scope: str,
        workspace_id: str | None,
        ids: list[str],
        action: str,
        expected_revision: int,
    ) -> dict[str, object]:
        self._validate_scope(scope, workspace_id)
        if (
            type(ids) is not list
            or not ids
            or any(type(identifier) is not str for identifier in ids)
            or len(set(ids)) != len(ids)
        ):
            raise AgentError("invalid_request")
        if action not in {"enable", "disable", "remove"}:
            raise AgentError("invalid_request")
        with self.lock:
            catalog = self._catalog()
            self._expected(catalog, expected_revision)
            selected: list[AgentRecord] = []
            for identifier in ids:
                try:
                    item = self._find(catalog, identifier)
                except AgentError as error:
                    if error.code == "not_found":
                        raise AgentError("invalid_request") from None
                    raise
                if item.scope != scope or item.workspaceId != workspace_id:
                    raise AgentError("invalid_request")
                selected.append(item)
            actions: list[dict[str, object]] = []
            affected = 0
            selected_ids = {item.id for item in selected}
            next_records: list[AgentRecord] = []
            for item in catalog.agents:
                if item.id not in selected_ids:
                    next_records.append(item)
                    continue
                if action == "remove":
                    actions.append(self._archive_action(item))
                    affected += 1
                    continue
                desired = action == "enable"
                if item.enabled != desired:
                    next_records.append(item.model_copy(update={"enabled": desired, "revision": item.revision + 1}))
                    affected += 1
                else:
                    next_records.append(item)
            if affected == 0:
                return {"revision": catalog.revision, "affected": 0}
            updated = catalog.model_copy(
                update={"revision": catalog.revision + 1, "agents": tuple(next_records)}
            )
            self._commit(updated, actions)
            return {"revision": updated.revision, "affected": affected}

    def remove_workspace(self, workspace_id: str) -> None:
        self._validate_scope("workspace", workspace_id)
        with self.lock:
            catalog = self._catalog()
            remaining = tuple(item for item in catalog.agents if item.workspaceId != workspace_id)
            if len(remaining) == len(catalog.agents):
                return
            updated = catalog.model_copy(
                update={"revision": catalog.revision + 1, "agents": remaining}
            )
            self._commit(updated, [])

    def snapshot(self, workspace_id: str) -> AgentExecutionSnapshot:
        if type(workspace_id) is not str:
            raise AgentError("workspace_unavailable")
        with self.lock:
            catalog = self._catalog()
            _, decisions = self._decisions(catalog, workspace_id, "workspace")
            return execution_snapshot(decisions)

    # ----- small pure helpers ------------------------------------------------

    def _scan_base(self, scope: str, workspace_id: str | None) -> Path:
        if scope == "global":
            return self.paths.agents_dir
        context = self._workspace_context(workspace_id or "")
        if context.availability is not WorkspaceAvailability.AVAILABLE or context.root_path is None:
            raise AgentError("workspace_unavailable")
        return self.paths.workspace_agents_dir(Path(context.root_path))

    def _has_duplicate_name(
        self,
        peers: tuple[AgentRecord, ...],
        name_key: str,
        *,
        workspace_id: str | None,
    ) -> bool:
        context = (
            self._workspace_context(workspace_id)
            if workspace_id is not None
            else None
        )
        for item in peers:
            candidate, _ = self._load_candidate(item, context=context)
            if candidate.name_key == name_key:
                return True
        return False

    @staticmethod
    def _write_action(record: AgentRecord, raw: bytes) -> dict[str, object]:
        return {
            "action": "write",
            "record": record.model_dump(mode="json"),
            "content": base64.b64encode(raw).decode("ascii"),
        }

    @staticmethod
    def _archive_action(record: AgentRecord) -> dict[str, object]:
        return {
            "action": "archive",
            "record": record.model_dump(mode="json"),
            "archiveId": str(uuid4()),
        }
