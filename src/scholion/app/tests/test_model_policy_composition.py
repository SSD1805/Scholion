from pathlib import Path
from typing import Any, cast

from scholion.app.app_container import _create_model_manager
from scholion.model_management.catalog import ModelCatalog
from scholion.model_management.models import ModelSpec
from scholion.model_management.service import ModelManager
from scholion.supply_chain import ModelTrustCatalog, TrustedModelFile, TrustedModelSpec


def _catalog() -> ModelCatalog:
    return ModelCatalog(
        (
            ModelSpec(
                model_id="tiny",
                engine="faster-whisper",
                repository_id="Systran/faster-whisper-tiny",
                estimated_cache_bytes=100,
                quality_rank=1,
            ),
        )
    )


def _trust_catalog() -> ModelTrustCatalog:
    return ModelTrustCatalog(
        schema_version=1,
        models=(
            TrustedModelSpec(
                model_id="tiny",
                engine="faster-whisper",
                repository_id="Systran/faster-whisper-tiny",
                revision="a" * 40,
                source_url="https://huggingface.co/Systran/faster-whisper-tiny",
                license_id="test",
                license_url="https://example.test/license",
                files=(
                    TrustedModelFile(
                        path="model.bin",
                        size_bytes=1,
                        sha256_hex="b" * 64,
                    ),
                ),
            ),
        ),
    )


def _manager(tmp_path: Path, trust_catalog: ModelTrustCatalog | None) -> ModelManager:
    return _create_model_manager(
        catalog=_catalog(),
        provider=cast(Any, object()),
        file_store=cast(Any, object()),
        model_root=tmp_path / "models",
        storage_admitter=cast(Any, object()),
        trust_catalog=trust_catalog,
    )


def test_source_build_without_packaged_policy_keeps_enforcement_off(
    tmp_path: Path,
) -> None:
    manager = _manager(tmp_path, None)

    assert manager.trust_catalog is None
    assert manager.enforce_policy_trust is False


def test_packaged_policy_automatically_enables_enforcement(tmp_path: Path) -> None:
    trust_catalog = _trust_catalog()

    manager = _manager(tmp_path, trust_catalog)

    assert manager.trust_catalog is trust_catalog
    assert manager.enforce_policy_trust is True
