"""Roll-forward catalog/credential transaction with encrypted secret staging."""

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from opensprite_backend.atomic_file import atomic_write
from opensprite_backend.credentials import CredentialStore
from .catalog_models import BUILTIN_PROVIDER_IDS, valid_provider_id
from .catalog_store import CatalogError, JsonProviderCatalog, ProviderCatalog


class PendingCatalogTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    provider_id: str
    staging_id: str | None
    remove_secret: bool
    previous_revision: int = Field(ge=0)
    target: ProviderCatalog


class ProviderCatalogTransaction:
    def __init__(self, catalog: JsonProviderCatalog, credentials: CredentialStore, path: Path) -> None:
        self.catalog = catalog
        self.credentials = credentials
        self.path = path

    def commit(self, target: ProviderCatalog, provider_id: str, *, expected_revision: int, secret: str | None = None, remove_secret: bool = False) -> None:
        with self.catalog.gate:
            self.recover()
            if self.catalog.get().revision != expected_revision:
                raise CatalogError("revision_conflict")
            if target.revision != expected_revision + 1 or not valid_provider_id(provider_id) or provider_id in BUILTIN_PROVIDER_IDS or (secret is not None and remove_secret):
                raise CatalogError("invalid_request")
            staging = str(uuid4()) if secret is not None else None
            pending = PendingCatalogTransaction(provider_id=provider_id, staging_id=staging, remove_secret=remove_secret, previous_revision=expected_revision, target=target)
            try:
                if staging is not None:
                    self.credentials.set(f"provider:{staging}:bearer", secret)
                atomic_write(self.path, pending.model_dump_json().encode("utf-8"))
            except Exception:
                if staging is not None and not self.path.exists():
                    try:
                        self.credentials.delete(f"provider:{staging}:bearer")
                    except Exception:
                        pass
                raise CatalogError from None
            finally:
                secret = None
            self.recover()

    def recover(self) -> None:
        with self.catalog.gate:
            try:
                raw = self.path.read_bytes()
            except FileNotFoundError:
                return
            except OSError:
                raise CatalogError from None
            try:
                import json
                from .catalog_store import _strict_pairs
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError("oversized_transaction")
                json.loads(raw, object_pairs_hook=_strict_pairs)
                pending = PendingCatalogTransaction.model_validate_json(raw)
                if not valid_provider_id(pending.provider_id) or pending.provider_id in BUILTIN_PROVIDER_IDS:
                    raise ValueError("invalid_provider_id")
                if pending.staging_id is not None and (not valid_provider_id(pending.staging_id) or pending.staging_id in BUILTIN_PROVIDER_IDS):
                    raise ValueError("invalid_staging_id")
                current = self.catalog.get()
                if pending.target.revision != pending.previous_revision + 1 or current.revision not in (pending.previous_revision, pending.target.revision):
                    raise ValueError("invalid_transaction_revision")
                if current.revision == pending.target.revision:
                    if current != pending.target:
                        raise ValueError("transaction_conflict")
                else:
                    destination = f"provider:{pending.provider_id}:bearer"
                    if pending.staging_id is not None:
                        secret = self.credentials.get(f"provider:{pending.staging_id}:bearer")
                        if secret is None:
                            raise ValueError("missing_staged_secret")
                        try:
                            self.credentials.set(destination, secret)
                        finally:
                            secret = None
                    elif pending.remove_secret:
                        self.credentials.delete(destination)
                    self.catalog.replace(pending.target, expected_revision=pending.previous_revision)
                if pending.staging_id is not None:
                    self.credentials.delete(f"provider:{pending.staging_id}:bearer")
                self.path.unlink()
            except Exception:
                raise CatalogError from None
