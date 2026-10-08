"""Fixed import, inventory, cache removal and Docker bundle operations."""

from typing import Protocol

from .deployment import deployment_bundle
from .inspection import inspect_wheel
from .models import ExecutionPackageError, PackageListResponse, PackageSummary
from .runtime_identity import RuntimePackageIdentity
from .store import ExecutionPackageStore


class ExecutionPackageOperations(Protocol):
    def list(self) -> PackageListResponse: ...
    def import_wheel(self, file_name: str, data: bytes) -> PackageListResponse: ...
    def delete(self, package_id: str) -> None: ...
    def bundle(self, package_id: str) -> bytes: ...


class ExecutionPackageService:
    def __init__(self, paths, *, base_image_ref=None, runtime_kind="local", manifest_path=None,
                 distribution_lookup=None):
        self.store = ExecutionPackageStore(paths)
        arguments = {} if distribution_lookup is None else {"distribution_lookup": distribution_lookup}
        self.identity = RuntimePackageIdentity(base_image_ref=base_image_ref, runtime_kind=runtime_kind,
                                              manifest_path=manifest_path, **arguments)

    def list(self) -> PackageListResponse:
        packages = self.store.list()
        runtime, manifest = self.identity.snapshot()
        result = []
        for stored in packages:
            summary = stored.inspection.model_dump(exclude={"files"})
            result.append(PackageSummary(id=stored.id, importedAt=stored.importedAt, **summary,
                runtimeStatus=self.identity.package_status(stored.inspection, manifest)))
        return PackageListResponse(packages=result, runtime=runtime)

    def import_wheel(self, file_name: str, data: bytes) -> PackageListResponse:
        inspected = inspect_wheel(data, file_name)
        self.store.save(inspected, data)
        return self.list()

    def delete(self, package_id: str) -> None:
        self.store.delete(package_id)

    def bundle(self, package_id: str) -> bytes:
        stored, wheel = self.store.get(package_id)
        if any(plugin.apiVersion != 2 for plugin in stored.inspection.plugins):
            raise ExecutionPackageError("incompatible_package")
        if self.identity.kind != "docker":
            raise ExecutionPackageError("deployment_unavailable")
        return deployment_bundle(stored, wheel, self.identity.base_image)


class UnavailableExecutionPackages:
    def list(self):
        raise ExecutionPackageError("packages_store_unavailable")

    def import_wheel(self, file_name, data):
        raise ExecutionPackageError("packages_store_unavailable")

    def delete(self, package_id):
        raise ExecutionPackageError("packages_store_unavailable")

    def bundle(self, package_id):
        raise ExecutionPackageError("deployment_unavailable")
