from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scholion.supply_chain.digests import sha256_file
from scholion.supply_chain.release_version import validate_release_version
from scholion.supply_chain.update_manifest import (
    ReleaseArtifact,
    SignedUpdateEnvelope,
    UpdateManifestPayload,
)


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{field} must be an explicit UTC timestamp")


@dataclass(frozen=True, slots=True)
class ReleaseArtifactInput:
    platform: str
    path: Path
    url: str

    def __post_init__(self) -> None:
        resolved = self.path.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("release artifact input must be a regular file")
        object.__setattr__(self, "path", resolved)


def measure_release_artifact(item: ReleaseArtifactInput) -> ReleaseArtifact:
    return ReleaseArtifact(
        platform=item.platform,
        url=item.url,
        size_bytes=item.path.stat().st_size,
        sha256_hex=sha256_file(item.path),
    )


def build_update_payload_bytes(
    *,
    sequence: int,
    channel: str,
    version: str,
    published_at: datetime,
    expires_at: datetime,
    release_notes_url: str,
    artifacts: tuple[ReleaseArtifactInput, ...],
) -> bytes:
    """Build the exact deterministic bytes that an offline release key signs."""
    if channel != "stable":
        raise ValueError("first-release metadata tooling only emits the stable channel")
    validate_release_version(version)
    _require_utc(published_at, "published_at")
    _require_utc(expires_at, "expires_at")

    measured = tuple(measure_release_artifact(item) for item in artifacts)
    payload_document = {
        "schema_version": 1,
        "sequence": sequence,
        "channel": channel,
        "version": version,
        "published_at": published_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "release_notes_url": release_notes_url,
        "artifacts": [
            {
                "platform": artifact.platform,
                "url": artifact.url,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256_hex,
            }
            for artifact in sorted(measured, key=lambda value: value.platform)
        ],
    }
    payload = json.dumps(
        payload_document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    # Re-parse through the runtime schema so release tooling cannot emit a shape the
    # client would reject after signature verification.
    UpdateManifestPayload.from_bytes(payload)
    return payload


def assemble_signed_update_envelope(
    payload: bytes,
    *,
    key_id: str,
    signature: bytes,
) -> bytes:
    """Wrap an externally produced Ed25519 signature around exact payload bytes."""
    envelope = SignedUpdateEnvelope(
        schema_version=1,
        key_id=key_id,
        algorithm="ed25519",
        payload=payload,
        signature=signature,
    )
    document = {
        "schema_version": envelope.schema_version,
        "key_id": envelope.key_id,
        "algorithm": envelope.algorithm,
        "payload_base64": base64.b64encode(envelope.payload).decode("ascii"),
        "signature_base64": base64.b64encode(envelope.signature).decode("ascii"),
    }
    return (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_sha256sums(artifacts: tuple[ReleaseArtifactInput, ...]) -> bytes:
    """Build deterministic public checksums without treating them as a signature."""
    names = tuple(item.path.name for item in artifacts)
    if len(names) != len(set(names)):
        raise ValueError("release artifact filenames must be unique for SHA256SUMS")
    lines = [
        f"{sha256_file(item.path)}  {item.path.name}"
        for item in sorted(artifacts, key=lambda value: value.path.name)
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")
