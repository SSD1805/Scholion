import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from scholion.supply_chain.update_manifest import (
    UpdateTrustError,
    verify_signed_update_manifest,
)


class FixtureVerifier:
    def __init__(self, *, accepted_key: str, accepted_payload: bytes, accepted_signature: bytes) -> None:
        self.accepted_key = accepted_key
        self.accepted_payload = accepted_payload
        self.accepted_signature = accepted_signature
        self.calls = 0

    def verify(
        self,
        *,
        key_id: str,
        algorithm: str,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        self.calls += 1
        return (
            key_id == self.accepted_key
            and algorithm == "ed25519"
            and payload == self.accepted_payload
            and signature == self.accepted_signature
        )


def _payload(*, sequence: int = 7, expires_delta: timedelta = timedelta(days=7)) -> bytes:
    now = datetime(2026, 8, 23, 15, 0, tzinfo=timezone.utc)
    document = {
        "schema_version": 1,
        "sequence": sequence,
        "channel": "stable",
        "version": "0.2.0",
        "published_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + expires_delta).isoformat().replace("+00:00", "Z"),
        "release_notes_url": "https://updates.example.invalid/releases/0.2.0",
        "artifacts": [
            {
                "platform": "linux-x86_64",
                "url": "https://updates.example.invalid/artifacts/scholion-linux-x86_64.tar.zst",
                "size_bytes": 42,
                "sha256": "a" * 64,
            }
        ],
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _envelope(payload: bytes, *, key_id: str = "release-2026", signature: bytes | None = None) -> dict[str, object]:
    resolved_signature = signature if signature is not None else b"s" * 64
    return {
        "schema_version": 1,
        "key_id": key_id,
        "algorithm": "ed25519",
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "signature_base64": base64.b64encode(resolved_signature).decode("ascii"),
    }


def test_signature_is_verified_before_payload_can_authorize_release() -> None:
    payload = _payload()
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )

    manifest = verify_signed_update_manifest(
        _envelope(payload, signature=signature),
        verifier=verifier,
        now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        highest_seen_sequence=7,
    )

    assert verifier.calls == 1
    assert manifest.version == "0.2.0"
    assert manifest.artifact_for("linux-x86_64").sha256_hex == "a" * 64


def test_modified_payload_fails_existing_signature() -> None:
    payload = _payload()
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )
    tampered = payload.replace(b"0.2.0", b"9.9.9")

    with pytest.raises(UpdateTrustError, match="signature verification failed"):
        verify_signed_update_manifest(
            _envelope(tampered, signature=signature),
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_unknown_signing_key_fails_closed() -> None:
    payload = _payload()
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )

    with pytest.raises(UpdateTrustError, match="signature verification failed"):
        verify_signed_update_manifest(
            _envelope(payload, key_id="unknown-key", signature=signature),
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_rollback_sequence_is_rejected_after_signature_verification() -> None:
    payload = _payload(sequence=6)
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )

    with pytest.raises(UpdateTrustError, match="older than a previously trusted sequence"):
        verify_signed_update_manifest(
            _envelope(payload, signature=signature),
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
            highest_seen_sequence=7,
        )

    assert verifier.calls == 1


def test_expired_metadata_is_rejected() -> None:
    payload = _payload(expires_delta=timedelta(hours=1))
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )

    with pytest.raises(UpdateTrustError, match="expired"):
        verify_signed_update_manifest(
            _envelope(payload, signature=signature),
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_artifact_transport_must_be_https_and_typed() -> None:
    payload_document = json.loads(_payload().decode("utf-8"))
    payload_document["artifacts"][0]["url"] = "http://updates.example.invalid/app"
    payload = json.dumps(payload_document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = b"s" * 64
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=signature,
    )

    with pytest.raises(UpdateTrustError, match="HTTPS URL"):
        verify_signed_update_manifest(
            _envelope(payload, signature=signature),
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_envelope_rejects_unmodeled_remote_configuration() -> None:
    payload = _payload()
    envelope = _envelope(payload)
    envelope["command"] = "run-this"
    verifier = FixtureVerifier(
        accepted_key="release-2026",
        accepted_payload=payload,
        accepted_signature=b"s" * 64,
    )

    with pytest.raises(UpdateTrustError, match="unexpected fields"):
        verify_signed_update_manifest(
            envelope,
            verifier=verifier,
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )
