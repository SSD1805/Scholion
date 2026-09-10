from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scholion.supply_chain.catalog_loader import parse_model_trust_catalog
from scholion.supply_chain.model_trust import ModelTrustCatalog

_SCHEMA_VERSION = 1
_UPDATE_KEY_CATALOG_NAME = "update-keys.json"
_MODEL_TRUST_CATALOG_NAME = "model-trust.json"
_EVIDENCE_NAME = "release-trust-inputs.json"
_MAX_UPDATE_KEY_CATALOG_BYTES = 32 * 1024
_MAX_MODEL_TRUST_CATALOG_BYTES = 2 * 1024 * 1024
_MAX_EVIDENCE_BYTES = 256 * 1024
_KEY_ID_RE = re.compile(r"^[a-z0-9._-]{1,64}$")
_LOWER_HEX_32_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseTrustInputError(ValueError):
    """Raised when release-owned trust material is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class PreparedReleaseTrustInputs:
    directory: Path
    update_keys: Path
    model_trust: Path
    evidence: Path


def _read_bounded(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        resolved = path.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise ReleaseTrustInputError(f"{label} must be a regular file")
        size = resolved.stat().st_size
        if size < 1 or size > maximum:
            raise ReleaseTrustInputError(f"{label} exceeded its bounded size")
        return resolved.read_bytes()
    except OSError as exc:
        raise ReleaseTrustInputError(f"{label} is unavailable") from exc


def _prepared_payload(root: Path, name: str, *, maximum: int, label: str) -> bytes:
    candidate = root / name
    if candidate.is_symlink():
        raise ReleaseTrustInputError(f"{label} must not be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ReleaseTrustInputError(f"{label} is unavailable") from exc
    if not resolved.is_relative_to(root):
        raise ReleaseTrustInputError(f"{label} escaped the prepared trust directory")
    return _read_bounded(resolved, maximum=maximum, label=label)


def _output_file(directory: Path, name: str) -> Path:
    candidate = directory / name
    if candidate.is_symlink():
        candidate.unlink()
    elif candidate.exists():
        if not candidate.is_file():
            raise ReleaseTrustInputError(
                "prepared trust output path is not a regular file"
            )
        candidate.unlink()
    return candidate


def _require_exact_keys(
    document: dict[str, Any], expected: set[str], *, label: str
) -> None:
    if set(document) != expected:
        raise ReleaseTrustInputError(f"{label} has unexpected fields")


def _parse_update_key_catalog(payload: bytes) -> tuple[tuple[str, str], ...]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseTrustInputError(
            "update key catalog must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ReleaseTrustInputError("update key catalog must be a JSON object")
    _require_exact_keys(
        document, {"schema_version", "keys"}, label="update key catalog"
    )
    if document.get("schema_version") != _SCHEMA_VERSION:
        raise ReleaseTrustInputError("unsupported update key catalog schema version")

    raw_keys = document.get("keys")
    if not isinstance(raw_keys, list) or not 1 <= len(raw_keys) <= 2:
        raise ReleaseTrustInputError("update key catalog must contain one or two keys")

    identities: list[tuple[str, str]] = []
    public_keys: set[str] = set()
    current_count = 0
    for raw in raw_keys:
        if not isinstance(raw, dict):
            raise ReleaseTrustInputError("update key records must be objects")
        _require_exact_keys(
            raw,
            {"key_id", "algorithm", "public_key_hex", "state"},
            label="update key record",
        )
        key_id = raw.get("key_id")
        algorithm = raw.get("algorithm")
        public_key = raw.get("public_key_hex")
        state = raw.get("state")
        if not isinstance(key_id, str) or _KEY_ID_RE.fullmatch(key_id) is None:
            raise ReleaseTrustInputError("update key ID is invalid")
        if algorithm != "ed25519":
            raise ReleaseTrustInputError("update key algorithm must be ed25519")
        if (
            not isinstance(public_key, str)
            or _LOWER_HEX_32_RE.fullmatch(public_key) is None
        ):
            raise ReleaseTrustInputError(
                "update public key must be exactly 32 lowercase-hex bytes"
            )
        if state not in {"current", "next"}:
            raise ReleaseTrustInputError("update key state must be current or next")
        if any(existing_id == key_id for existing_id, _ in identities):
            raise ReleaseTrustInputError("update key IDs must be unique")
        if public_key in public_keys:
            raise ReleaseTrustInputError("update public keys must be unique")
        public_keys.add(public_key)
        current_count += int(state == "current")
        identities.append((key_id, state))

    if current_count != 1:
        raise ReleaseTrustInputError(
            "update key catalog must contain exactly one current key"
        )
    return tuple(identities)


def _parse_model_catalog(payload: bytes) -> ModelTrustCatalog:
    try:
        return parse_model_trust_catalog(payload)
    except ValueError as exc:
        raise ReleaseTrustInputError("model trust catalog is invalid") from exc


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _evidence_document(
    *,
    update_payload: bytes,
    key_identities: tuple[tuple[str, str], ...],
    model_payload: bytes,
    catalog: ModelTrustCatalog,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "inputs": {
            "update_keys": {
                "filename": _UPDATE_KEY_CATALOG_NAME,
                "size_bytes": len(update_payload),
                "sha256": _sha256(update_payload),
                "keys": [
                    {"key_id": key_id, "state": state}
                    for key_id, state in key_identities
                ],
            },
            "model_trust": {
                "filename": _MODEL_TRUST_CATALOG_NAME,
                "size_bytes": len(model_payload),
                "sha256": _sha256(model_payload),
                "models": [
                    {
                        "model_id": model.model_id,
                        "engine": model.engine,
                        "repository_id": model.repository_id,
                        "revision": model.revision,
                        "license_id": model.license_id,
                    }
                    for model in catalog.models
                ],
            },
        },
    }


def prepare_release_trust_inputs(
    *,
    update_key_catalog: Path,
    model_trust_catalog: Path,
    output_dir: Path,
) -> PreparedReleaseTrustInputs:
    """Validate and stage exact release trust bytes with deterministic evidence."""
    update_payload = _read_bounded(
        update_key_catalog,
        maximum=_MAX_UPDATE_KEY_CATALOG_BYTES,
        label="update key catalog",
    )
    model_payload = _read_bounded(
        model_trust_catalog,
        maximum=_MAX_MODEL_TRUST_CATALOG_BYTES,
        label="model trust catalog",
    )
    key_identities = _parse_update_key_catalog(update_payload)
    catalog = _parse_model_catalog(model_payload)
    evidence = _evidence_document(
        update_payload=update_payload,
        key_identities=key_identities,
        model_payload=model_payload,
        catalog=catalog,
    )

    destination = output_dir.expanduser().resolve(strict=False)
    destination.mkdir(parents=True, exist_ok=True)
    if not destination.is_dir():
        raise ReleaseTrustInputError("prepared trust output must be a directory")
    update_output = _output_file(destination, _UPDATE_KEY_CATALOG_NAME)
    model_output = _output_file(destination, _MODEL_TRUST_CATALOG_NAME)
    evidence_output = _output_file(destination, _EVIDENCE_NAME)
    update_output.write_bytes(update_payload)
    model_output.write_bytes(model_payload)
    evidence_output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return PreparedReleaseTrustInputs(
        directory=destination,
        update_keys=update_output,
        model_trust=model_output,
        evidence=evidence_output,
    )


def verify_prepared_release_trust_inputs(directory: Path) -> PreparedReleaseTrustInputs:
    """Re-verify prepared trust bytes against their deterministic evidence."""
    try:
        resolved = directory.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ReleaseTrustInputError("prepared trust directory is unavailable") from exc
    if not resolved.is_dir():
        raise ReleaseTrustInputError("prepared trust directory must be a directory")

    update_path = resolved / _UPDATE_KEY_CATALOG_NAME
    model_path = resolved / _MODEL_TRUST_CATALOG_NAME
    evidence_path = resolved / _EVIDENCE_NAME
    update_payload = _prepared_payload(
        resolved,
        _UPDATE_KEY_CATALOG_NAME,
        maximum=_MAX_UPDATE_KEY_CATALOG_BYTES,
        label="prepared update key catalog",
    )
    model_payload = _prepared_payload(
        resolved,
        _MODEL_TRUST_CATALOG_NAME,
        maximum=_MAX_MODEL_TRUST_CATALOG_BYTES,
        label="prepared model trust catalog",
    )
    evidence_payload = _prepared_payload(
        resolved,
        _EVIDENCE_NAME,
        maximum=_MAX_EVIDENCE_BYTES,
        label="release trust evidence",
    )
    key_identities = _parse_update_key_catalog(update_payload)
    catalog = _parse_model_catalog(model_payload)
    expected = _evidence_document(
        update_payload=update_payload,
        key_identities=key_identities,
        model_payload=model_payload,
        catalog=catalog,
    )
    try:
        observed = json.loads(evidence_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseTrustInputError(
            "release trust evidence is unavailable or invalid"
        ) from exc
    if observed != expected:
        raise ReleaseTrustInputError(
            "prepared release trust bytes do not match their evidence"
        )
    return PreparedReleaseTrustInputs(
        directory=resolved,
        update_keys=update_path,
        model_trust=model_path,
        evidence=evidence_path,
    )


def install_prepared_release_trust_inputs(
    runtime_dir: Path,
    prepared_dir: Path,
) -> None:
    """Install only verified trust files into their fixed frozen-runtime locations."""
    runtime = runtime_dir.expanduser().resolve(strict=True)
    internal = runtime / "_internal"
    if not runtime.is_dir() or not internal.is_dir():
        raise ReleaseTrustInputError("frozen runtime layout is unavailable")
    prepared = verify_prepared_release_trust_inputs(prepared_dir)

    model_destination = internal / "scholion" / "supply_chain" / _MODEL_TRUST_CATALOG_NAME
    model_destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        model_parent = model_destination.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseTrustInputError("frozen model trust destination is unavailable") from exc
    if not model_parent.is_relative_to(runtime):
        raise ReleaseTrustInputError("frozen model trust destination escaped the runtime")
    if model_destination.is_symlink():
        model_destination.unlink()
    elif model_destination.exists():
        if not model_destination.is_file():
            raise ReleaseTrustInputError("frozen model trust destination is not a file")
        model_destination.unlink()
    shutil.copy2(prepared.model_trust, model_destination)

    public_destination = runtime / "release-trust"
    if public_destination.is_symlink():
        public_destination.unlink()
    else:
        shutil.rmtree(public_destination, ignore_errors=True)
    public_destination.mkdir()
    shutil.copy2(prepared.update_keys, public_destination / _UPDATE_KEY_CATALOG_NAME)
    shutil.copy2(prepared.evidence, public_destination / _EVIDENCE_NAME)
