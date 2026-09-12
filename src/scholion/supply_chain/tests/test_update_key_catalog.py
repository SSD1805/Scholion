from __future__ import annotations

import json
from pathlib import Path

import pytest

from scholion.supply_chain.release_trust_inputs import ReleaseTrustInputError
from scholion.supply_chain.update_key_catalog import (
    build_update_key_catalog,
    ed25519_public_key_hex_from_spki_der,
)

_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


def _write_public_key(path: Path, byte: int) -> Path:
    path.write_bytes(_SPKI_PREFIX + bytes([byte]) * 32)
    return path


def test_extracts_exact_ed25519_spki_public_key() -> None:
    payload = _SPKI_PREFIX + bytes.fromhex("11" * 32)
    assert ed25519_public_key_hex_from_spki_der(payload) == "11" * 32


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        bytes.fromhex("11" * 32),
        b"-----BEGIN PRIVATE KEY-----\nnot-a-public-key\n",
        bytes.fromhex("302a300506032b6571032100") + bytes.fromhex("11" * 32),
        _SPKI_PREFIX + bytes.fromhex("11" * 31),
        _SPKI_PREFIX + bytes.fromhex("11" * 33),
    ],
    ids=[
        "empty",
        "raw-32-bytes",
        "private-pem-shape",
        "wrong-algorithm-oid",
        "short-key",
        "long-key",
    ],
)
def test_rejects_non_ed25519_public_spki(payload: bytes) -> None:
    with pytest.raises(ReleaseTrustInputError):
        ed25519_public_key_hex_from_spki_der(payload)


def test_builds_deterministic_current_key_catalog(tmp_path: Path) -> None:
    public_key = _write_public_key(tmp_path / "current.der", 0x22)

    payload = build_update_key_catalog(
        current_key_id="release-2026-a",
        current_public_key_der=public_key,
    )

    assert json.loads(payload) == {
        "schema_version": 1,
        "keys": [
            {
                "algorithm": "ed25519",
                "key_id": "release-2026-a",
                "public_key_hex": "22" * 32,
                "state": "current",
            }
        ],
    }
    assert payload.endswith(b"\n")
    assert payload == build_update_key_catalog(
        current_key_id="release-2026-a",
        current_public_key_der=public_key,
    )


def test_builds_current_and_next_rotation_catalog(tmp_path: Path) -> None:
    current = _write_public_key(tmp_path / "current.der", 0x33)
    next_key = _write_public_key(tmp_path / "next.der", 0x44)

    payload = build_update_key_catalog(
        current_key_id="release-2026-a",
        current_public_key_der=current,
        next_key_id="release-2027-a",
        next_public_key_der=next_key,
    )

    assert [item["state"] for item in json.loads(payload)["keys"]] == [
        "current",
        "next",
    ]


def test_requires_complete_next_key_pair(tmp_path: Path) -> None:
    current = _write_public_key(tmp_path / "current.der", 0x55)
    next_key = _write_public_key(tmp_path / "next.der", 0x66)

    with pytest.raises(ReleaseTrustInputError, match="supplied together"):
        build_update_key_catalog(
            current_key_id="release-2026-a",
            current_public_key_der=current,
            next_key_id="release-2027-a",
        )

    with pytest.raises(ReleaseTrustInputError, match="supplied together"):
        build_update_key_catalog(
            current_key_id="release-2026-a",
            current_public_key_der=current,
            next_public_key_der=next_key,
        )


def test_reuses_existing_catalog_validation(tmp_path: Path) -> None:
    current = _write_public_key(tmp_path / "current.der", 0x77)
    duplicate = _write_public_key(tmp_path / "next.der", 0x77)

    with pytest.raises(ReleaseTrustInputError, match="unique"):
        build_update_key_catalog(
            current_key_id="release-2026-a",
            current_public_key_der=current,
            next_key_id="release-2027-a",
            next_public_key_der=duplicate,
        )

    with pytest.raises(ReleaseTrustInputError, match="ID is invalid"):
        build_update_key_catalog(
            current_key_id="Release 2026 A",
            current_public_key_der=current,
        )
