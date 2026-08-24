import json
from pathlib import Path

import pytest

from scholion.model_management.catalog import ModelCatalog
from scholion.model_management.errors import ModelManagementError
from scholion.model_management.models import InstalledSnapshot, ModelSpec
from scholion.model_management.service import ModelManager
from scholion.supply_chain import ModelTrustCatalog, TrustedModelFile, TrustedModelSpec

_REVISION = "a" * 40


class _Store:
    def __init__(self) -> None:
        self.files: dict[Path, bytes] = {}

    def ensure_directory_exists(
        self, directory_path: str | Path, *, private: bool = False
    ) -> None:
        assert private

    def save_file(
        self, content: bytes, file_path: str | Path, *, private: bool = False
    ) -> None:
        assert private
        self.files[Path(file_path)] = content

    def read_file(self, file_path: str | Path) -> bytes:
        return self.files[Path(file_path)]

    def file_exists(self, file_path: str | Path) -> bool:
        return Path(file_path) in self.files

    def delete_file(self, file_path: str | Path) -> None:
        self.files.pop(Path(file_path), None)


class _Provider:
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path
        self.removed: list[str] = []

    def install(
        self,
        spec: ModelSpec,
        *,
        cache_root: Path,
        revision: str | None,
    ) -> InstalledSnapshot:
        return InstalledSnapshot(
            resolved_revision=revision or "legacy-revision",
            snapshot_path=self.snapshot_path,
            size_bytes=10,
            verification="test-local-validation",
        )

    def validate(
        self,
        spec: ModelSpec,
        snapshot: InstalledSnapshot,
        *,
        cache_root: Path,
    ) -> None:
        assert snapshot.snapshot_path.is_relative_to(cache_root)

    def remove(
        self,
        snapshot: InstalledSnapshot,
        *,
        cache_root: Path,
    ) -> None:
        assert snapshot.snapshot_path.is_relative_to(cache_root)
        self.removed.append(snapshot.resolved_revision)


def _catalog() -> ModelCatalog:
    return ModelCatalog(
        (
            ModelSpec(
                model_id="small",
                engine="faster-whisper",
                repository_id="Systran/faster-whisper-small",
                estimated_cache_bytes=100,
                quality_rank=1,
                required_files=("model.bin",),
            ),
        )
    )


def _trust_catalog() -> ModelTrustCatalog:
    return ModelTrustCatalog(
        schema_version=1,
        models=(
            TrustedModelSpec(
                model_id="small",
                engine="faster-whisper",
                repository_id="Systran/faster-whisper-small",
                revision=_REVISION,
                source_url="https://huggingface.co/Systran/faster-whisper-small",
                license_id="test",
                license_url="https://example.test/license",
                files=(
                    TrustedModelFile(
                        path="model.bin",
                        size_bytes=1,
                        sha256_hex="0" * 64,
                    ),
                ),
            ),
        ),
    )


def _legacy_manifest(manager: ModelManager, store: _Store) -> None:
    store.files[manager._manifest_path("small")] = json.dumps(
        {
            "schema_version": 1,
            "model_id": "small",
            "engine": "faster-whisper",
            "repository_id": "Systran/faster-whisper-small",
            "requested_revision": None,
            "resolved_revision": "legacy-revision",
            "snapshot_path": str(manager.cache_root / "snapshots" / "legacy-revision"),
            "size_bytes": 10,
            "verification": "test-local-validation",
            "policy_trust": None,
        }
    ).encode("utf-8")


def _enforcing_manager(tmp_path: Path) -> tuple[ModelManager, _Store, _Provider]:
    root = tmp_path / "models"
    provider = _Provider(root / "faster-whisper" / "snapshots" / "legacy-revision")
    store = _Store()
    manager = ModelManager(
        catalog=_catalog(),
        provider=provider,
        file_store=store,
        model_root=root,
        trust_catalog=_trust_catalog(),
        enforce_policy_trust=True,
    )
    _legacy_manifest(manager, store)
    return manager, store, provider


def test_enforcement_keeps_legacy_model_visible_but_not_policy_trusted(
    tmp_path: Path,
) -> None:
    manager, _, _ = _enforcing_manager(tmp_path)

    item = manager.inventory()[0]

    assert item.installed is True
    assert item.manifest is not None
    assert item.manifest.resolved_revision == "legacy-revision"
    assert item.policy_trusted is False


def test_enforcement_refuses_legacy_model_for_new_execution(tmp_path: Path) -> None:
    manager, _, _ = _enforcing_manager(tmp_path)

    with pytest.raises(ModelManagementError, match="registry is invalid"):
        manager.resolved_revision("small")


def test_enforcement_allows_legacy_model_removal_for_replacement(tmp_path: Path) -> None:
    manager, store, provider = _enforcing_manager(tmp_path)

    removed = manager.remove("small")

    assert removed.resolved_revision == "legacy-revision"
    assert provider.removed == ["legacy-revision"]
    assert manager._manifest_path("small") not in store.files
