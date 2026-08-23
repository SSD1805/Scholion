from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

_MODEL_CATALOG_SCHEMA_VERSION = 1
_MODEL_VERIFICATION_METHOD = "scholion_curated_sha256_v1"
_SHA256_HEX_LENGTH = 64
_GIT_REVISION_HEX_LENGTH = 40
_READ_CHUNK_BYTES = 1024 * 1024


def _require_exact_keys(document: dict[str, Any], expected: set[str]) -> None:
    actual = set(document)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ValueError("unexpected trust-manifest fields: " + "; ".join(details))


def _require_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _require_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _require_https_url(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an HTTPS URL")


def _require_lower_hex(value: str, *, length: int, field: str) -> None:
    if len(value) != length or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field} must be {length} lowercase hexadecimal characters")


@dataclass(frozen=True, slots=True)
class TrustedModelFile:
    path: str
    size_bytes: int
    sha256_hex: str

    def __post_init__(self) -> None:
        if not self.path or "\\" in self.path:
            raise ValueError("trusted model file path must use non-empty POSIX syntax")
        pure = PurePosixPath(self.path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError("trusted model file path must stay inside the snapshot")
        if self.size_bytes < 1:
            raise ValueError("trusted model file size must be positive")
        _require_lower_hex(self.sha256_hex, length=_SHA256_HEX_LENGTH, field="sha256")

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> TrustedModelFile:
        _require_exact_keys(document, {"path", "size_bytes", "sha256"})
        return cls(
            path=_require_str(document, "path"),
            size_bytes=_require_int(document, "size_bytes"),
            sha256_hex=_require_str(document, "sha256"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256_hex,
        }


@dataclass(frozen=True, slots=True)
class TrustedModelSpec:
    model_id: str
    engine: str
    repository_id: str
    revision: str
    source_url: str
    license_id: str
    license_url: str
    files: tuple[TrustedModelFile, ...]

    def __post_init__(self) -> None:
        for field in ("model_id", "engine", "repository_id", "license_id"):
            value = getattr(self, field)
            if not value.strip():
                raise ValueError(f"{field} cannot be empty")
        _require_lower_hex(
            self.revision,
            length=_GIT_REVISION_HEX_LENGTH,
            field="model revision",
        )
        _require_https_url(self.source_url, "source_url")
        _require_https_url(self.license_url, "license_url")
        if not self.files:
            raise ValueError("trusted model must declare at least one file")
        paths = tuple(item.path for item in self.files)
        if len(paths) != len(set(paths)):
            raise ValueError("trusted model file paths must be unique")

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> TrustedModelSpec:
        _require_exact_keys(
            document,
            {
                "model_id",
                "engine",
                "repository_id",
                "revision",
                "source_url",
                "license_id",
                "license_url",
                "files",
            },
        )
        raw_files = document.get("files")
        if not isinstance(raw_files, list) or any(not isinstance(item, dict) for item in raw_files):
            raise ValueError("files must be a list of objects")
        return cls(
            model_id=_require_str(document, "model_id"),
            engine=_require_str(document, "engine"),
            repository_id=_require_str(document, "repository_id"),
            revision=_require_str(document, "revision"),
            source_url=_require_str(document, "source_url"),
            license_id=_require_str(document, "license_id"),
            license_url=_require_str(document, "license_url"),
            files=tuple(TrustedModelFile.from_dict(item) for item in raw_files),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "engine": self.engine,
            "repository_id": self.repository_id,
            "revision": self.revision,
            "source_url": self.source_url,
            "license_id": self.license_id,
            "license_url": self.license_url,
            "files": [item.to_dict() for item in self.files],
        }


@dataclass(frozen=True, slots=True)
class ModelTrustCatalog:
    schema_version: int
    models: tuple[TrustedModelSpec, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _MODEL_CATALOG_SCHEMA_VERSION:
            raise ValueError("unsupported model trust catalog schema version")
        if not self.models:
            raise ValueError("model trust catalog cannot be empty")
        model_ids = tuple(item.model_id for item in self.models)
        if len(model_ids) != len(set(model_ids)):
            raise ValueError("trusted model IDs must be unique")

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> ModelTrustCatalog:
        _require_exact_keys(document, {"schema_version", "models"})
        raw_models = document.get("models")
        if not isinstance(raw_models, list) or any(not isinstance(item, dict) for item in raw_models):
            raise ValueError("models must be a list of objects")
        return cls(
            schema_version=_require_int(document, "schema_version"),
            models=tuple(TrustedModelSpec.from_dict(item) for item in raw_models),
        )

    def require(self, model_id: str) -> TrustedModelSpec:
        match = next((item for item in self.models if item.model_id == model_id), None)
        if match is None:
            raise ValueError(f"model is not trusted by Scholion policy: {model_id}")
        return match

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "models": [item.to_dict() for item in self.models],
        }


@dataclass(frozen=True, slots=True)
class ModelTrustEvidence:
    model_id: str
    repository_id: str
    revision: str
    verification: str
    verified_files: int
    total_bytes: int


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_trusted_model_snapshot(
    spec: TrustedModelSpec,
    *,
    snapshot_root: Path,
    cache_root: Path,
) -> ModelTrustEvidence:
    resolved_snapshot = snapshot_root.expanduser().resolve(strict=True)
    resolved_cache = cache_root.expanduser().resolve(strict=True)
    if not resolved_snapshot.is_dir() or not resolved_snapshot.is_relative_to(resolved_cache):
        raise ValueError("trusted model snapshot must be a directory inside the model cache")

    declared_paths = {item.path for item in spec.files}
    observed_paths = {
        path.relative_to(resolved_snapshot).as_posix()
        for path in resolved_snapshot.rglob("*")
        if path.is_file()
    }
    if observed_paths != declared_paths:
        missing = sorted(declared_paths - observed_paths)
        extra = sorted(observed_paths - declared_paths)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("undeclared=" + ",".join(extra))
        raise ValueError("model snapshot file set does not match trusted policy: " + "; ".join(details))

    total_bytes = 0
    for trusted_file in spec.files:
        candidate = resolved_snapshot.joinpath(*PurePosixPath(trusted_file.path).parts)
        if not candidate.is_file():
            raise ValueError(f"trusted model file is missing: {trusted_file.path}")
        resolved_candidate = candidate.resolve(strict=True)
        if not resolved_candidate.is_relative_to(resolved_cache):
            raise ValueError("trusted model file resolves outside the model cache")
        size_bytes = candidate.stat().st_size
        if size_bytes != trusted_file.size_bytes:
            raise ValueError(f"trusted model file size mismatch: {trusted_file.path}")
        if _hash_file(candidate) != trusted_file.sha256_hex:
            raise ValueError(f"trusted model file hash mismatch: {trusted_file.path}")
        total_bytes += size_bytes

    return ModelTrustEvidence(
        model_id=spec.model_id,
        repository_id=spec.repository_id,
        revision=spec.revision,
        verification=_MODEL_VERIFICATION_METHOD,
        verified_files=len(spec.files),
        total_bytes=total_bytes,
    )
