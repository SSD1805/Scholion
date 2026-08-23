"""Supply-chain trust primitives for models and application releases."""

from scholion.supply_chain.model_trust import (
    ModelTrustCatalog,
    ModelTrustEvidence,
    TrustedModelFile,
    TrustedModelSpec,
    verify_trusted_model_snapshot,
)
from scholion.supply_chain.update_manifest import (
    ReleaseArtifact,
    SignedUpdateEnvelope,
    UpdateManifestPayload,
    UpdateTrustError,
    verify_signed_update_manifest,
)

__all__ = [
    "ModelTrustCatalog",
    "ModelTrustEvidence",
    "ReleaseArtifact",
    "SignedUpdateEnvelope",
    "TrustedModelFile",
    "TrustedModelSpec",
    "UpdateManifestPayload",
    "UpdateTrustError",
    "verify_signed_update_manifest",
    "verify_trusted_model_snapshot",
]
