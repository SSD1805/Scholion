from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

_ENVELOPE_SCHEMA_VERSION = 1
_PAYLOAD_SCHEMA_VERSION = 1
_MAX_PAYLOAD_BYTES = 64 * 1024
_SHA256_HEX_LENGTH = 64
_ED25519_SIGNATURE_BYTES = 64
_ALLOWED_SIGNATURE_ALGORITHM = "ed25519"


class UpdateTrustError(ValueError):
    """Raised when signed update metadata cannot authorize an update."""


class SignatureVerifier(Protocol):
    def verify(
        self,
        *,
        key_id: str,
        algorithm: str,
        payload: bytes,
        signature: bytes,
    ) -> bool: ...


def _require_exact_keys(document: dict[str, Any], expected: set[str]) -> None:
    actual = set(document)
    if actual != expected:
        raise UpdateTrustError("update metadata contains unexpected fields")


def _require_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UpdateTrustError(f"{key} must be a non-empty string")
    return value


def _require_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise UpdateTrustError(f"{key} must be an integer")
    return value


def _require_identifier(value: str, field: str) -> None:
    if len(value) > 64 or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in value
    ):
        raise UpdateTrustError(f"{field} contains unsupported characters")


def _require_https_url(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise UpdateTrustError(f"{field} must be an HTTPS URL without embedded credentials")


def _require_sha256(value: str) -> None:
    if len(value) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise UpdateTrustError("artifact sha256 must be 64 lowercase hexadecimal characters")


def _parse_utc_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UpdateTrustError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise UpdateTrustError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _decode_base64(value: str, field: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise UpdateTrustError(f"{field} must be valid base64") from exc


@dataclass(frozen=True, slots=True)
class ReleaseArtifact:
    platform: str
    url: str
    size_bytes: int
    sha256_hex: str

    def __post_init__(self) -> None:
        _require_identifier(self.platform, "platform")
        _require_https_url(self.url, "artifact url")
        if self.size_bytes < 1:
            raise UpdateTrustError("artifact size must be positive")
        _require_sha256(self.sha256_hex)

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> ReleaseArtifact:
        _require_exact_keys(document, {"platform", "url", "size_bytes", "sha256"})
        return cls(
            platform=_require_str(document, "platform"),
            url=_require_str(document, "url"),
            size_bytes=_require_int(document, "size_bytes"),
            sha256_hex=_require_str(document, "sha256"),
        )


@dataclass(frozen=True, slots=True)
class UpdateManifestPayload:
    schema_version: int
    sequence: int
    channel: str
    version: str
    published_at: datetime
    expires_at: datetime
    release_notes_url: str
    artifacts: tuple[ReleaseArtifact, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _PAYLOAD_SCHEMA_VERSION:
            raise UpdateTrustError("unsupported update payload schema version")
        if self.sequence < 1:
            raise UpdateTrustError("update sequence must be positive")
        _require_identifier(self.channel, "channel")
        if not self.version.strip() or len(self.version) > 128:
            raise UpdateTrustError("version must be a bounded non-empty string")
        _require_https_url(self.release_notes_url, "release notes url")
        if self.expires_at <= self.published_at:
            raise UpdateTrustError("update metadata must expire after publication")
        if not self.artifacts:
            raise UpdateTrustError("update metadata must contain at least one artifact")
        platforms = tuple(item.platform for item in self.artifacts)
        if len(platforms) != len(set(platforms)):
            raise UpdateTrustError("update artifact platforms must be unique")

    @classmethod
    def from_bytes(cls, payload: bytes) -> UpdateManifestPayload:
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateTrustError("signed update payload is not valid UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise UpdateTrustError("signed update payload must be a JSON object")
        _require_exact_keys(
            document,
            {
                "schema_version",
                "sequence",
                "channel",
                "version",
                "published_at",
                "expires_at",
                "release_notes_url",
                "artifacts",
            },
        )
        raw_artifacts = document.get("artifacts")
        if not isinstance(raw_artifacts, list) or any(
            not isinstance(item, dict) for item in raw_artifacts
        ):
            raise UpdateTrustError("artifacts must be a list of objects")
        return cls(
            schema_version=_require_int(document, "schema_version"),
            sequence=_require_int(document, "sequence"),
            channel=_require_str(document, "channel"),
            version=_require_str(document, "version"),
            published_at=_parse_utc_timestamp(
                _require_str(document, "published_at"), "published_at"
            ),
            expires_at=_parse_utc_timestamp(
                _require_str(document, "expires_at"), "expires_at"
            ),
            release_notes_url=_require_str(document, "release_notes_url"),
            artifacts=tuple(ReleaseArtifact.from_dict(item) for item in raw_artifacts),
        )

    def artifact_for(self, platform: str) -> ReleaseArtifact:
        match = next((item for item in self.artifacts if item.platform == platform), None)
        if match is None:
            raise UpdateTrustError(f"release does not contain an artifact for {platform}")
        return match


@dataclass(frozen=True, slots=True)
class SignedUpdateEnvelope:
    schema_version: int
    key_id: str
    algorithm: str
    payload: bytes
    signature: bytes

    def __post_init__(self) -> None:
        if self.schema_version != _ENVELOPE_SCHEMA_VERSION:
            raise UpdateTrustError("unsupported update envelope schema version")
        _require_identifier(self.key_id, "key_id")
        if self.algorithm != _ALLOWED_SIGNATURE_ALGORITHM:
            raise UpdateTrustError("unsupported update signature algorithm")
        if not self.payload or len(self.payload) > _MAX_PAYLOAD_BYTES:
            raise UpdateTrustError("signed update payload exceeds its size boundary")
        if len(self.signature) != _ED25519_SIGNATURE_BYTES:
            raise UpdateTrustError("update signature has an invalid length")

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> SignedUpdateEnvelope:
        _require_exact_keys(
            document,
            {"schema_version", "key_id", "algorithm", "payload_base64", "signature_base64"},
        )
        return cls(
            schema_version=_require_int(document, "schema_version"),
            key_id=_require_str(document, "key_id"),
            algorithm=_require_str(document, "algorithm"),
            payload=_decode_base64(_require_str(document, "payload_base64"), "payload_base64"),
            signature=_decode_base64(
                _require_str(document, "signature_base64"), "signature_base64"
            ),
        )


def verify_signed_update_manifest(
    document: dict[str, Any],
    *,
    verifier: SignatureVerifier,
    now: datetime,
    highest_seen_sequence: int | None = None,
) -> UpdateManifestPayload:
    envelope = SignedUpdateEnvelope.from_dict(document)
    if not verifier.verify(
        key_id=envelope.key_id,
        algorithm=envelope.algorithm,
        payload=envelope.payload,
        signature=envelope.signature,
    ):
        raise UpdateTrustError("update manifest signature verification failed")

    payload = UpdateManifestPayload.from_bytes(envelope.payload)
    if now.tzinfo is None:
        raise UpdateTrustError("current time must include a timezone")
    resolved_now = now.astimezone(timezone.utc)
    if payload.expires_at <= resolved_now:
        raise UpdateTrustError("update metadata has expired")
    if payload.published_at > resolved_now:
        raise UpdateTrustError("update metadata publication time is in the future")
    if highest_seen_sequence is not None and payload.sequence < highest_seen_sequence:
        raise UpdateTrustError("update metadata is older than a previously trusted sequence")
    return payload
