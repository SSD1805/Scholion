from pathlib import Path

import pytest

from scholion.model_management.models import (
    InstalledSnapshot,
    ManagedModelManifest,
    ManagedModelPolicyTrust,
    ModelInventoryItem,
    ModelSpec,
)


def _policy_trust() -> ManagedModelPolicyTrust:
    return ManagedModelPolicyTrust(
        catalog_schema_version=1,
        model_id="small",
        revision="abc123",
        verification="scholion_curated_sha256_v1",
        verified_files=4,
        total_bytes=123,
    )


def _manifest(
    *, policy_trust: ManagedModelPolicyTrust | None = None
) -> ManagedModelManifest:
    return ManagedModelManifest(
        schema_version=1,
        model_id="small",
        engine="faster-whisper",
        repository_id="Systran/faster-whisper-small",
        requested_revision="release-v1",
        resolved_revision="abc123",
        snapshot_path=Path("cache/models/faster-whisper/snapshots/abc123"),
        size_bytes=123,
        verification="required_files_v1",
        policy_trust=policy_trust,
    )


def test_manifest_round_trip_preserves_model_provenance() -> None:
    manifest = _manifest()

    restored = ManagedModelManifest.from_dict(manifest.to_dict())

    assert restored == manifest
    assert restored.requested_revision == "release-v1"
    assert restored.resolved_revision == "abc123"
    assert restored.verification == "required_files_v1"
    assert restored.policy_trust is None


def test_manifest_round_trip_preserves_policy_trust_evidence() -> None:
    manifest = _manifest(policy_trust=_policy_trust())

    restored = ManagedModelManifest.from_dict(manifest.to_dict())

    assert restored == manifest
    assert restored.policy_trust is not None
    assert restored.policy_trust.verification == "scholion_curated_sha256_v1"
    assert restored.policy_trust.verified_files == 4


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("model_id", 7),
        ("size_bytes", "123"),
        ("requested_revision", 7),
        ("verification", ""),
        ("policy_trust", "trusted"),
    ],
)
def test_manifest_parser_rejects_schema_and_type_mutations(
    key: str, value: object
) -> None:
    document = _manifest().to_dict()
    document[key] = value

    with pytest.raises(ValueError, match="invalid model manifest"):
        ManagedModelManifest.from_dict(document)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"catalog_schema_version": 0}, "catalog_schema_version must be positive"),
        ({"model_id": ""}, "model_id cannot be empty"),
        ({"revision": " "}, "revision cannot be empty"),
        ({"verification": ""}, "verification cannot be empty"),
        ({"verified_files": 0}, "verified_files must be positive"),
        ({"total_bytes": 0}, "total_bytes must be positive"),
    ],
)
def test_policy_trust_rejects_invalid_evidence_boundaries(
    overrides: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "catalog_schema_version": 1,
        "model_id": "small",
        "revision": "abc123",
        "verification": "scholion_curated_sha256_v1",
        "verified_files": 1,
        "total_bytes": 1,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        ManagedModelPolicyTrust(**values)  # type: ignore[arg-type]


def test_policy_trust_parser_wraps_missing_or_mistyped_fields() -> None:
    with pytest.raises(ValueError, match="invalid model policy trust evidence"):
        ManagedModelPolicyTrust.from_dict({"catalog_schema_version": 1})
    with pytest.raises(ValueError, match="invalid model policy trust evidence"):
        ManagedModelPolicyTrust.from_dict(
            {
                "catalog_schema_version": True,
                "model_id": "small",
                "revision": "abc123",
                "verification": "scholion_curated_sha256_v1",
                "verified_files": 1,
                "total_bytes": 1,
            }
        )


def test_manifest_rejects_policy_trust_for_different_revision() -> None:
    trust = ManagedModelPolicyTrust(
        catalog_schema_version=1,
        model_id="small",
        revision="different",
        verification="scholion_curated_sha256_v1",
        verified_files=1,
        total_bytes=1,
    )

    with pytest.raises(ValueError, match="policy trust revision"):
        _manifest(policy_trust=trust)


def test_manifest_rejects_policy_trust_for_different_model() -> None:
    trust = ManagedModelPolicyTrust(
        catalog_schema_version=1,
        model_id="medium",
        revision="abc123",
        verification="scholion_curated_sha256_v1",
        verified_files=1,
        total_bytes=1,
    )

    with pytest.raises(ValueError, match="policy trust model identity"):
        _manifest(policy_trust=trust)


def test_manifest_rejects_empty_requested_revision_and_nonpositive_size() -> None:
    with pytest.raises(ValueError, match="requested_revision cannot be empty"):
        ManagedModelManifest(
            schema_version=1,
            model_id="small",
            engine="faster-whisper",
            repository_id="repo/small",
            requested_revision=" ",
            resolved_revision="abc123",
            snapshot_path=Path("snapshot"),
            size_bytes=1,
            verification="required_files_v1",
        )
    with pytest.raises(ValueError, match="size_bytes must be positive"):
        ManagedModelManifest(
            schema_version=1,
            model_id="small",
            engine="faster-whisper",
            repository_id="repo/small",
            requested_revision=None,
            resolved_revision="abc123",
            snapshot_path=Path("snapshot"),
            size_bytes=0,
            verification="required_files_v1",
        )


def test_model_spec_rejects_storage_and_identity_boundaries() -> None:
    with pytest.raises(ValueError, match="estimated_cache_bytes must be positive"):
        ModelSpec("small", "faster-whisper", "repo/small", 0, 1)
    with pytest.raises(ValueError, match="quality_rank cannot be negative"):
        ModelSpec("small", "faster-whisper", "repo/small", 1, -1)
    with pytest.raises(ValueError, match="model_id cannot be empty"):
        ModelSpec(" ", "faster-whisper", "repo/small", 1, 1)
    with pytest.raises(ValueError, match="filenames cannot be empty"):
        ModelSpec("small", "faster-whisper", "repo/small", 1, 1, ("",))


def test_installed_snapshot_rejects_empty_revision_verification_and_size() -> None:
    with pytest.raises(ValueError, match="resolved_revision cannot be empty"):
        InstalledSnapshot(" ", Path("snapshot"), 1, "verified")
    with pytest.raises(ValueError, match="size_bytes must be positive"):
        InstalledSnapshot("abc", Path("snapshot"), 0, "verified")
    with pytest.raises(ValueError, match="verification cannot be empty"):
        InstalledSnapshot("abc", Path("snapshot"), 1, " ")


def test_inventory_item_keeps_current_trust_separate_from_recorded_evidence() -> None:
    spec = ModelSpec("small", "faster-whisper", "repo/small", 1, 1)
    trusted_manifest = _manifest(policy_trust=_policy_trust())

    uninstalled = ModelInventoryItem(spec)
    installed = ModelInventoryItem(spec, _manifest())
    receipt_only = ModelInventoryItem(spec, trusted_manifest)
    trusted = ModelInventoryItem(spec, trusted_manifest, policy_trusted=True)

    assert uninstalled.installed is False
    assert installed.installed is True
    assert installed.policy_trusted is False
    assert receipt_only.policy_trusted is False
    assert trusted.policy_trusted is True
    assert uninstalled.to_dict()["manifest"] is None
    assert installed.to_dict()["manifest"] is not None
    assert trusted.to_dict()["policy_trusted"] is True


def test_inventory_item_rejects_current_trust_without_managed_state() -> None:
    spec = ModelSpec("small", "faster-whisper", "repo/small", 1, 1)

    with pytest.raises(ValueError, match="requires a managed manifest"):
        ModelInventoryItem(spec, policy_trusted=True)
