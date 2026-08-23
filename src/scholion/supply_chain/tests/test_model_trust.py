from hashlib import sha256
from pathlib import Path

import pytest

from scholion.supply_chain.model_trust import (
    ModelTrustCatalog,
    TrustedModelFile,
    TrustedModelSpec,
    verify_trusted_model_snapshot,
)


def _trusted_file(path: str, content: bytes) -> TrustedModelFile:
    return TrustedModelFile(
        path=path,
        size_bytes=len(content),
        sha256_hex=sha256(content).hexdigest(),
    )


def _spec(files: tuple[TrustedModelFile, ...]) -> TrustedModelSpec:
    return TrustedModelSpec(
        model_id="tiny",
        engine="faster-whisper",
        repository_id="example/faster-whisper-tiny",
        revision="a" * 40,
        source_url="https://example.invalid/models/tiny",
        license_id="MIT",
        license_url="https://example.invalid/licenses/mit",
        files=files,
    )


def test_catalog_requires_exact_trust_metadata() -> None:
    content = b"model"
    catalog = ModelTrustCatalog.from_dict(
        {
            "schema_version": 1,
            "models": [
                {
                    "model_id": "tiny",
                    "engine": "faster-whisper",
                    "repository_id": "example/faster-whisper-tiny",
                    "revision": "a" * 40,
                    "source_url": "https://example.invalid/models/tiny",
                    "license_id": "MIT",
                    "license_url": "https://example.invalid/licenses/mit",
                    "files": [
                        {
                            "path": "model.bin",
                            "size_bytes": len(content),
                            "sha256": sha256(content).hexdigest(),
                        }
                    ],
                }
            ],
        }
    )

    trusted = catalog.require("tiny")
    assert trusted.revision == "a" * 40
    assert trusted.files[0].sha256_hex == sha256(content).hexdigest()


def test_catalog_rejects_moving_or_ambiguous_revision() -> None:
    with pytest.raises(ValueError, match="model revision"):
        TrustedModelSpec(
            model_id="tiny",
            engine="faster-whisper",
            repository_id="example/faster-whisper-tiny",
            revision="main",
            source_url="https://example.invalid/models/tiny",
            license_id="MIT",
            license_url="https://example.invalid/licenses/mit",
            files=(_trusted_file("model.bin", b"model"),),
        )


def test_trusted_file_rejects_path_escape() -> None:
    with pytest.raises(ValueError, match="inside the snapshot"):
        TrustedModelFile(
            path="../private.txt",
            size_bytes=1,
            sha256_hex="0" * 64,
        )


def test_trusted_file_rejects_snapshot_root_as_file_path() -> None:
    with pytest.raises(ValueError, match="inside the snapshot"):
        TrustedModelFile(
            path=".",
            size_bytes=1,
            sha256_hex="0" * 64,
        )


def test_snapshot_verification_checks_exact_file_set_hash_and_size(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache"
    snapshot = cache_root / "snapshots" / ("a" * 40)
    snapshot.mkdir(parents=True)
    model = b"model-bytes"
    config = b"{}"
    (snapshot / "model.bin").write_bytes(model)
    (snapshot / "config.json").write_bytes(config)
    spec = _spec(
        (
            _trusted_file("model.bin", model),
            _trusted_file("config.json", config),
        )
    )

    evidence = verify_trusted_model_snapshot(
        spec,
        snapshot_root=snapshot,
        cache_root=cache_root,
    )

    assert evidence.verification == "scholion_curated_sha256_v1"
    assert evidence.verified_files == 2
    assert evidence.total_bytes == len(model) + len(config)

    (snapshot / "model.bin").write_bytes(b"other-bytes")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_trusted_model_snapshot(
            spec, snapshot_root=snapshot, cache_root=cache_root
        )


def test_snapshot_verification_rejects_size_mismatch(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    snapshot = cache_root / "snapshots" / ("a" * 40)
    snapshot.mkdir(parents=True)
    model = b"model"
    (snapshot / "model.bin").write_bytes(model)
    spec = _spec((_trusted_file("model.bin", model),))

    (snapshot / "model.bin").write_bytes(b"model-expanded")

    with pytest.raises(ValueError, match="size mismatch"):
        verify_trusted_model_snapshot(
            spec, snapshot_root=snapshot, cache_root=cache_root
        )


def test_snapshot_verification_rejects_undeclared_file(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    snapshot = cache_root / "snapshots" / ("a" * 40)
    snapshot.mkdir(parents=True)
    model = b"model"
    (snapshot / "model.bin").write_bytes(model)
    (snapshot / "surprise.json").write_text("{}", encoding="utf-8")
    spec = _spec((_trusted_file("model.bin", model),))

    with pytest.raises(ValueError, match="undeclared=surprise.json"):
        verify_trusted_model_snapshot(
            spec, snapshot_root=snapshot, cache_root=cache_root
        )


def test_snapshot_verification_rejects_snapshot_outside_cache(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    snapshot = tmp_path / "elsewhere"
    snapshot.mkdir()
    model = b"model"
    (snapshot / "model.bin").write_bytes(model)
    spec = _spec((_trusted_file("model.bin", model),))

    with pytest.raises(ValueError, match="inside the model cache"):
        verify_trusted_model_snapshot(
            spec, snapshot_root=snapshot, cache_root=cache_root
        )
