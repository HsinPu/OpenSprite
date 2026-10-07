"""Fixed HTTP and cache shapes for one imported execution-plugin wheel."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_WHEEL_BYTES = 10 * 1024 * 1024
MAX_UNPACKED_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_FILES = 512
MAX_PACKAGES = 64


class ExecutionPackageError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PackagePlugin(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$", max_length=64)
    kind: Literal["loop", "policy"]
    apiVersion: int = Field(ge=1)
    entryPoint: str = Field(min_length=1, max_length=256)


class PackageFile(StrictModel):
    path: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sizeBytes: int = Field(ge=0, le=MAX_FILE_BYTES)


class WheelInspection(StrictModel):
    fileName: str = Field(min_length=1, max_length=255)
    distributionName: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sizeBytes: int = Field(ge=1, le=MAX_WHEEL_BYTES)
    requiresPython: str | None
    requiresDist: list[str]
    plugins: list[PackagePlugin]
    files: list[PackageFile]


class StoredPackage(StrictModel):
    schemaVersion: Literal[1]
    id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    importedAt: str
    inspection: WheelInspection


class PackageSummary(StrictModel):
    id: str
    fileName: str
    distributionName: str
    version: str
    sha256: str
    sizeBytes: int
    importedAt: str
    requiresPython: str | None
    requiresDist: list[str]
    plugins: list[PackagePlugin]
    runtimeStatus: Literal["not_installed", "confirmed", "unverified", "mismatch"]


class RuntimeIdentity(StrictModel):
    kind: Literal["docker", "local"]
    baseImage: str | None
    manifestStatus: Literal["verified", "missing", "invalid"]


class PackageListResponse(StrictModel):
    packages: list[PackageSummary]
    runtime: RuntimeIdentity


class DeploymentPackage(StrictModel):
    distributionName: str
    version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    plugins: list[PackagePlugin]
    files: list[PackageFile]


class DeploymentManifest(StrictModel):
    schemaVersion: Literal[1]
    baseImage: str
    packages: list[DeploymentPackage]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def validate_imported_time(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("invalid import time")
