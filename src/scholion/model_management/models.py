from dataclasses import dataclass
from pathlib import Path


def _required_str(document: dict[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _required_int(document: dict[str, object], key: str) -> int:
    value = document[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    engine: str
    repository_id: str
    estimated_cache_bytes: int
    quality_rank: int
    required_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("model_id", "engine", "repository_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")
        if self.estimated_cache_bytes < 1:
            raise ValueError("estimated_cache_bytes must be positive")
        if self.quality_rank < 0:
            raise ValueError("quality_rank cannot be negative")
        if any(not name.strip() for name in self.required_files):
            raise ValueError("required model filenames cannot be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "engine": self.engine,
            "repository_id": self.repository_id,
            "estimated_cache_bytes": self.estimated_cache_bytes,
            "quality_rank": self.quality_rank,
            "required_files": list(self.required_files),
        }


@dataclass(frozen=True, slots=True)
class InstalledSnapshot:
    resolved_revision: str
    snapshot_path: Path
    size_bytes: int
    verification: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_path",
            self.snapshot_path.expanduser().resolve(strict=False),
        )
        if not self.resolved_revision.strip():
            raise ValueError("resolved_revision cannot be empty")
        if self.size_bytes < 1:
            raise ValueError("size_bytes must be positive")
        if not self.verification.strip():
            raise ValueError("verification cannot be empty")


@dataclass(frozen=True, slots=True)
class ManagedModelPolicyTrust:
    """Persisted evidence that a managed snapshot matched the bundled policy catalog."""

    catalog_schema_version: int
    model_id: str
    revision: str
    verification: str
    verified_files: int
    total_bytes: int

    def __post_init__(self) -> None:
        if self.catalog_schema_version < 1:
            raise ValueError("catalog_schema_version must be positive")
        for name in ("model_id", "revision", "verification"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")
        if self.verified_files < 1:
            raise ValueError("verified_files must be positive")
        if self.total_bytes < 1:
            raise ValueError("total_bytes must be positive")

    def to_dict(self) -> dict[str, object]:
        return {
            "catalog_schema_version": self.catalog_schema_version,
            "model_id": self.model_id,
            "revision": self.revision,
            "verification": self.verification,
            "verified_files": self.verified_files,
            "total_bytes": self.total_bytes,
        }

    @classmethod
    def from_dict(cls, document: dict[str, object]) -> "ManagedModelPolicyTrust":
        try:
            return cls(
                catalog_schema_version=_required_int(
                    document, "catalog_schema_version"
                ),
                model_id=_required_str(document, "model_id"),
                revision=_required_str(document, "revision"),
                verification=_required_str(document, "verification"),
                verified_files=_required_int(document, "verified_files"),
                total_bytes=_required_int(document, "total_bytes"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid model policy trust evidence") from exc


@dataclass(frozen=True, slots=True)
class ManagedModelManifest:
    schema_version: int
    model_id: str
    engine: str
    repository_id: str
    requested_revision: str | None
    resolved_revision: str
    snapshot_path: Path
    size_bytes: int
    verification: str
    policy_trust: ManagedModelPolicyTrust | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported model manifest schema version")
        for name in (
            "model_id",
            "engine",
            "repository_id",
            "resolved_revision",
            "verification",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")
        if self.requested_revision is not None and not self.requested_revision.strip():
            raise ValueError("requested_revision cannot be empty")
        object.__setattr__(
            self,
            "snapshot_path",
            self.snapshot_path.expanduser().resolve(strict=False),
        )
        if self.size_bytes < 1:
            raise ValueError("size_bytes must be positive")
        if self.policy_trust is not None:
            if self.policy_trust.model_id != self.model_id:
                raise ValueError("policy trust model identity does not match manifest")
            if self.policy_trust.revision != self.resolved_revision:
                raise ValueError("policy trust revision does not match manifest")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "engine": self.engine,
            "repository_id": self.repository_id,
            "requested_revision": self.requested_revision,
            "resolved_revision": self.resolved_revision,
            "snapshot_path": str(self.snapshot_path),
            "size_bytes": self.size_bytes,
            "verification": self.verification,
            "policy_trust": (
                None if self.policy_trust is None else self.policy_trust.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, document: dict[str, object]) -> "ManagedModelManifest":
        try:
            requested = document.get("requested_revision")
            if requested is not None and not isinstance(requested, str):
                raise ValueError("requested_revision must be a string or null")
            raw_policy_trust = document.get("policy_trust")
            if raw_policy_trust is not None and not isinstance(raw_policy_trust, dict):
                raise ValueError("policy_trust must be an object or null")
            return cls(
                schema_version=_required_int(document, "schema_version"),
                model_id=_required_str(document, "model_id"),
                engine=_required_str(document, "engine"),
                repository_id=_required_str(document, "repository_id"),
                requested_revision=requested,
                resolved_revision=_required_str(document, "resolved_revision"),
                snapshot_path=Path(_required_str(document, "snapshot_path")),
                size_bytes=_required_int(document, "size_bytes"),
                verification=_required_str(document, "verification"),
                policy_trust=(
                    None
                    if raw_policy_trust is None
                    else ManagedModelPolicyTrust.from_dict(raw_policy_trust)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid model manifest") from exc


@dataclass(frozen=True, slots=True)
class ModelInventoryItem:
    spec: ModelSpec
    manifest: ManagedModelManifest | None = None

    @property
    def installed(self) -> bool:
        return self.manifest is not None

    @property
    def policy_trusted(self) -> bool:
        return self.manifest is not None and self.manifest.policy_trust is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "spec": self.spec.to_dict(),
            "installed": self.installed,
            "policy_trusted": self.policy_trusted,
            "manifest": None if self.manifest is None else self.manifest.to_dict(),
        }
