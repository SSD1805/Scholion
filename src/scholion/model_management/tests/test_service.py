import json
from hashlib import sha256
from pathlib import Path

import pytest

from scholion.model_management.catalog import ModelCatalog
from scholion.model_management.errors import ModelManagementError
from scholion.model_management.models import InstalledSnapshot, ModelSpec
from scholion.model_management.service import ModelManager
from scholion.supply_chain import ModelTrustCatalog, TrustedModelFile, TrustedModelSpec

_TRUSTED_REVISION = "a" * 40
_TRUSTED_BYTES = b"trusted faster-whisper model bytes"


class MemoryStore:
    def __init__(self) -> None:
        self.files: dict[Path, bytes] = {}
        self.directories: set[Path] = set()

    def ensure_directory_exists(
        self, directory_path: str | Path, *, private: bool = False
    ) -> None:
        assert private
        self.directories.add(Path(directory_path))

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


class FakeProvider:
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path
        self.resolved_revision = snapshot_path.name
        self.size_bytes = 1234
        self.installs: list[tuple[str, str | None]] = []
        self.validations: list[str] = []
        self.removals: list[str] = []
        self.fail_validate = False
        self.fail_remove = False

    def install(
        self,
        spec: ModelSpec,
        *,
        cache_root: Path,
        revision: str | None,
    ) -> InstalledSnapshot:
        self.installs.append((spec.model_id, revision))
        return InstalledSnapshot(
            resolved_revision=self.resolved_revision,
            snapshot_path=self.snapshot_path,
            size_bytes=self.size_bytes,
            verification="fake_verified_v1",
        )

    def validate(
        self,
        spec: ModelSpec,
        snapshot: InstalledSnapshot,
        *,
        cache_root: Path,
    ) -> None:
        assert snapshot.snapshot_path.is_relative_to(cache_root)
        self.validations.append(spec.model_id)
        if self.fail_validate:
            raise ValueError("snapshot disappeared")

    def remove(
        self,
        snapshot: InstalledSnapshot,
        *,
        cache_root: Path,
    ) -> None:
        assert snapshot.snapshot_path.is_relative_to(cache_root)
        if self.fail_remove:
            raise RuntimeError("provider failed")
        self.removals.append(snapshot.resolved_revision)


def _catalog() -> ModelCatalog:
    return ModelCatalog(
        (
            ModelSpec(
                model_id="small",
                engine="faster-whisper",
                repository_id="Systran/faster-whisper-small",
                estimated_cache_bytes=750,
                quality_rank=2,
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
                revision=_TRUSTED_REVISION,
                source_url="https://huggingface.co/Systran/faster-whisper-small",
                license_id="test-license",
                license_url="https://example.test/license",
                files=(
                    TrustedModelFile(
                        path="model.bin",
                        size_bytes=len(_TRUSTED_BYTES),
                        sha256_hex=sha256(_TRUSTED_BYTES).hexdigest(),
                    ),
                ),
            ),
        ),
    )


def _manager(tmp_path: Path) -> tuple[ModelManager, MemoryStore, FakeProvider]:
    model_root = tmp_path / "models"
    provider = FakeProvider(
        model_root / "faster-whisper" / "snapshots" / "resolved-abc"
    )
    store = MemoryStore()
    return (
        ModelManager(
            catalog=_catalog(),
            provider=provider,
            file_store=store,
            model_root=model_root,
        ),
        store,
        provider,
    )


def _trusted_manager(
    tmp_path: Path, *, enforce_policy_trust: bool = True
) -> tuple[ModelManager, MemoryStore, FakeProvider, Path]:
    model_root = tmp_path / "models"
    snapshot_path = (
        model_root
        / "faster-whisper"
        / "models--Systran--faster-whisper-small"
        / "snapshots"
        / _TRUSTED_REVISION
    )
    snapshot_path.mkdir(parents=True)
    (snapshot_path / "model.bin").write_bytes(_TRUSTED_BYTES)
    provider = FakeProvider(snapshot_path)
    provider.size_bytes = len(_TRUSTED_BYTES)
    store = MemoryStore()
    manager = ModelManager(
        catalog=_catalog(),
        provider=provider,
        file_store=store,
        model_root=model_root,
        trust_catalog=_trust_catalog(),
        enforce_policy_trust=enforce_policy_trust,
    )
    return manager, store, provider, snapshot_path


def test_inventory_is_offline_read_only_and_reports_uninstalled_model(
    tmp_path: Path,
) -> None:
    manager, store, provider = _manager(tmp_path)

    inventory = manager.inventory()

    assert len(inventory) == 1
    assert inventory[0].spec.model_id == "small"
    assert inventory[0].installed is False
    assert inventory[0].policy_trusted is False
    assert provider.installs == []
    assert provider.validations == []
    assert store.directories == set()


def test_resolved_revision_lookup_is_read_only_when_unmanaged(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)

    assert manager.resolved_revision("small") is None
    assert store.directories == set()
    assert provider.installs == []
    assert provider.validations == []


def test_install_records_requested_resolved_and_verification(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)

    manifest = manager.install("small", revision="release-v1")

    assert manifest.requested_revision == "release-v1"
    assert manifest.resolved_revision == "resolved-abc"
    assert manifest.verification == "fake_verified_v1"
    assert manifest.policy_trust is None
    assert manifest.size_bytes == 1234
    assert provider.installs == [("small", "release-v1")]
    document = json.loads(store.files[manager._manifest_path("small")])
    assert document["repository_id"] == "Systran/faster-whisper-small"
    assert document["resolved_revision"] == "resolved-abc"
    assert document["verification"] == "fake_verified_v1"
    assert document["policy_trust"] is None
    assert manager.resolved_revision("small") == "resolved-abc"
    assert manager.is_installed("small") is True
    assert manager.is_policy_trusted("small") is False
    assert provider.validations == ["small", "small", "small"]


def test_policy_install_pins_revision_and_persists_exact_trust(tmp_path: Path) -> None:
    manager, store, provider, _ = _trusted_manager(tmp_path)

    manifest = manager.install("small")

    assert provider.installs == [("small", _TRUSTED_REVISION)]
    assert manifest.requested_revision == _TRUSTED_REVISION
    assert manifest.resolved_revision == _TRUSTED_REVISION
    assert manifest.policy_trust is not None
    assert manifest.policy_trust.model_id == "small"
    assert manifest.policy_trust.revision == _TRUSTED_REVISION
    assert manifest.policy_trust.verification == "scholion_curated_sha256_v1"
    assert manifest.policy_trust.verified_files == 1
    assert manifest.policy_trust.total_bytes == len(_TRUSTED_BYTES)
    document = json.loads(store.files[manager._manifest_path("small")])
    assert document["policy_trust"]["revision"] == _TRUSTED_REVISION
    assert manager.is_policy_trusted("small") is True
    assert manager.inventory()[0].policy_trusted is True


def test_recorded_policy_receipt_is_not_current_trust_without_catalog(
    tmp_path: Path,
) -> None:
    manager, store, provider, _ = _trusted_manager(tmp_path, enforce_policy_trust=False)
    manager.install("small")
    manager_without_catalog = ModelManager(
        catalog=_catalog(),
        provider=provider,
        file_store=store,
        model_root=manager.model_root,
    )

    assert manager_without_catalog.is_policy_trusted("small") is False
    assert manager_without_catalog.inventory()[0].policy_trusted is False


def test_policy_rejects_revision_override_before_provider_call(tmp_path: Path) -> None:
    manager, _, provider, _ = _trusted_manager(tmp_path)

    with pytest.raises(ValueError, match="does not match Scholion model policy"):
        manager.install("small", revision="b" * 40)

    assert provider.installs == []


def test_policy_hash_failure_does_not_register_model(tmp_path: Path) -> None:
    manager, store, provider, snapshot_path = _trusted_manager(tmp_path)
    (snapshot_path / "model.bin").write_bytes(b"tampered model bytes")

    with pytest.raises(ModelManagementError, match="downloaded and locally validated"):
        manager.install("small")

    assert provider.installs == [("small", _TRUSTED_REVISION)]
    assert manager._manifest_path("small") not in store.files


def test_policy_tamper_after_install_invalidates_registry(tmp_path: Path) -> None:
    manager, _, _, snapshot_path = _trusted_manager(tmp_path)
    manager.install("small")
    (snapshot_path / "model.bin").write_bytes(b"x" * len(_TRUSTED_BYTES))

    with pytest.raises(ModelManagementError, match="registry is invalid"):
        manager.is_policy_trusted("small")


def test_policy_enforcement_requires_catalog(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    provider = FakeProvider(model_root / "faster-whisper" / "snapshots" / "abc")

    with pytest.raises(ValueError, match="requires a trust catalog"):
        ModelManager(
            catalog=_catalog(),
            provider=provider,
            file_store=MemoryStore(),
            model_root=model_root,
            enforce_policy_trust=True,
        )


def test_install_rejects_empty_revision(tmp_path: Path) -> None:
    manager, _, provider = _manager(tmp_path)

    with pytest.raises(ValueError, match="revision cannot be empty"):
        manager.install("small", revision=" ")

    assert provider.installs == []


def test_stale_snapshot_is_not_reported_as_installed(tmp_path: Path) -> None:
    manager, _, provider = _manager(tmp_path)
    manager.install("small")
    provider.fail_validate = True

    with pytest.raises(ModelManagementError, match="registry is invalid"):
        manager.resolved_revision("small")


def test_remove_deletes_only_registered_snapshot(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    manager.install("small")

    removed = manager.remove("small")

    assert removed.model_id == "small"
    assert provider.removals == ["resolved-abc"]
    assert manager._manifest_path("small") not in store.files
    assert manager.is_installed("small") is False


def test_remove_failure_preserves_manifest(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    manager.install("small")
    provider.fail_remove = True

    with pytest.raises(ModelManagementError, match="removed safely"):
        manager.remove("small")

    assert manager._manifest_path("small") in store.files


def test_remove_refuses_unmanaged_model(tmp_path: Path) -> None:
    manager, _, provider = _manager(tmp_path)

    with pytest.raises(ValueError, match="not managed"):
        manager.remove("small")

    assert provider.removals == []


def test_install_refuses_snapshot_outside_cache(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    provider.snapshot_path = tmp_path / "escaped" / "resolved-abc"

    with pytest.raises(ModelManagementError, match="downloaded and locally validated"):
        manager.install("small")

    assert manager._manifest_path("small") not in store.files


def test_inventory_refuses_manifest_with_wrong_identity(tmp_path: Path) -> None:
    manager, store, _ = _manager(tmp_path)
    manager._prepare_roots()
    path = manager._manifest_path("small")
    store.files[path] = json.dumps(
        {
            "schema_version": 1,
            "model_id": "small",
            "engine": "faster-whisper",
            "repository_id": "attacker/wrong-model",
            "requested_revision": None,
            "resolved_revision": "resolved-abc",
            "snapshot_path": str(manager.cache_root / "snapshots" / "resolved-abc"),
            "size_bytes": 1234,
            "verification": "fake_verified_v1",
        }
    ).encode()

    with pytest.raises(ModelManagementError, match="registry is invalid"):
        manager.inventory()


def test_manifest_filename_rejects_unsafe_model_id(tmp_path: Path) -> None:
    manager, _, _ = _manager(tmp_path)

    with pytest.raises(ValueError, match="registry filename"):
        manager._manifest_path("../small")
