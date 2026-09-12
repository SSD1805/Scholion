from __future__ import annotations

import json
from pathlib import Path

from scholion.supply_chain.release_trust_inputs import (
    ReleaseTrustInputError,
    _parse_update_key_catalog,
)

_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")
_ED25519_SPKI_BYTES = len(_ED25519_SPKI_PREFIX) + 32


def ed25519_public_key_hex_from_spki_der(payload: bytes) -> str:
    """Extract an Ed25519 raw public key from the exact RFC 8410 SPKI shape."""
    if len(payload) != _ED25519_SPKI_BYTES or not payload.startswith(
        _ED25519_SPKI_PREFIX
    ):
        raise ReleaseTrustInputError(
            "Ed25519 public key must be an exact SubjectPublicKeyInfo DER document"
        )
    return payload[len(_ED25519_SPKI_PREFIX) :].hex()


def _public_key_hex(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise ReleaseTrustInputError("public key input must be a regular file")
        payload = resolved.read_bytes()
    except OSError as exc:
        raise ReleaseTrustInputError("public key input is unavailable") from exc
    return ed25519_public_key_hex_from_spki_der(payload)


def build_update_key_catalog(
    *,
    current_key_id: str,
    current_public_key_der: Path,
    next_key_id: str | None = None,
    next_public_key_der: Path | None = None,
) -> bytes:
    """Build a deterministic public-only Scholion update verification catalog."""
    if (next_key_id is None) != (next_public_key_der is None):
        raise ReleaseTrustInputError(
            "next key ID and next public key must be supplied together"
        )

    keys: list[dict[str, str]] = [
        {
            "algorithm": "ed25519",
            "key_id": current_key_id,
            "public_key_hex": _public_key_hex(current_public_key_der),
            "state": "current",
        }
    ]
    if next_key_id is not None and next_public_key_der is not None:
        keys.append(
            {
                "algorithm": "ed25519",
                "key_id": next_key_id,
                "public_key_hex": _public_key_hex(next_public_key_der),
                "state": "next",
            }
        )

    payload = (
        json.dumps(
            {"schema_version": 1, "keys": keys},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _parse_update_key_catalog(payload)
    return payload
