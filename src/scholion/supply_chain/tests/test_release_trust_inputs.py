from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scholion.supply_chain import release_trust_inputs
from scholion.supply_chain.release_trust_inputs import (
    ReleaseTrustInputError,
    install_prepared_release_trust_inputs,
    prepare_release_trust_inputs,
    verify_prepared_release_trust_inputs,
)

_RFC8032_PUBLIC_KEY = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
_OTHER_PUBLIC_KEY = "01" * 32


def _update_catalog(
    *,
    keys: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "keys": keys
        or [
            {
                "key_id": "release-2026-a",
                "algorithm": "ed25519",
                "public_key_hex": _RFC8032_PUBLIC_KEY,
                "state": "current",
            }
        ],
    }


def _key(
    *,
    key_id: str = "release-2026-a",
    public_key: str = _RFC8032_PUBLIC_KEY,
    state: str = "current",
    algorithm: str = "ed25519",
) -> dict[str, object]:
    return {
        "key_id": key_id,
        "algorithm": algorithm,
        "public_key_hex": public_key,
        "state": state,
    }


def _model_catalog() -> dict[str, object]:
    return {
        "schema_version": 1,
        "models": [
            {
                "model_id": "tiny",
                "engine": "faster-whisper",
                "repository_id": "reviewed/tiny",
                "revision": "1" * 40,
                "source_url": "https://example.invalid/reviewed/tiny",
                "license_id": "MIT",
                "license_url": "https://example.invalid/reviewed/tiny/license",
                "files": [
                    {
                        "path": "model.bin",
                        "size_bytes": 3,
                        "sha256": "a" * 64,
                    }
                ],
            }
        ],
    }


def _write_inputs(root: Path) -> tuple[Path, Path, bytes, bytes]:
    update_payload = (
        json.dumps(_update_catalog(), separators=(",", ":")).encode("utf-8") + b"\n"
    )
    model_payload = (
        json.dumps(_model_catalog(), separators=(",", ":")).encode("utf-8") + b"\n"
    )
    update_path = root / "approved-update-keys.json"
    model_path = root / "approved-model-trust.json"
    update_path.write_bytes(update_payload)
    model_path.write_bytes(model_payload)
    return update_path, model_path, update_payload, model_payload


def test_prepare_preserves_exact_bytes_and_emits_path_free_evidence(
    tmp_path: Path,
) -> None:
    update_path, model_path, update_payload, model_payload = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=tmp_path / "prepared",
    )

    assert prepared.update_keys.read_bytes() == update_payload
    assert prepared.model_trust.read_bytes() == model_payload
    evidence_bytes = prepared.evidence.read_bytes()
    evidence = json.loads(evidence_bytes)
    assert str(tmp_path) not in evidence_bytes.decode("utf-8")
    assert (
        evidence["inputs"]["update_keys"]["sha256"]
        == hashlib.sha256(update_payload).hexdigest()
    )
    assert (
        evidence["inputs"]["model_trust"]["sha256"]
        == hashlib.sha256(model_payload).hexdigest()
    )
    assert evidence["inputs"]["update_keys"]["keys"] == [
        {"key_id": "release-2026-a", "state": "current"}
    ]
    assert evidence["inputs"]["model_trust"]["models"][0]["revision"] == "1" * 40

    verified = verify_prepared_release_trust_inputs(prepared.directory)
    assert verified == prepared


def test_prepare_leaves_unrelated_output_files_untouched(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    output = tmp_path / "prepared"
    output.mkdir()
    unrelated = output / "unrelated.txt"
    unrelated.write_text("preserve me", encoding="utf-8")

    prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=output,
    )

    assert unrelated.read_text(encoding="utf-8") == "preserve me"


def test_install_copies_only_verified_allowlist_into_runtime(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=tmp_path / "prepared",
    )
    (prepared.directory / "stray.txt").write_text("do not bundle", encoding="utf-8")

    runtime = tmp_path / "runtime"
    (runtime / "_internal").mkdir(parents=True)
    release_trust = runtime / "release-trust"
    release_trust.mkdir()
    (release_trust / "stale.txt").write_text("remove me", encoding="utf-8")

    install_prepared_release_trust_inputs(runtime, prepared.directory)

    assert (
        runtime / "_internal" / "scholion" / "supply_chain" / "model-trust.json"
    ).read_bytes() == prepared.model_trust.read_bytes()
    assert (
        runtime / "release-trust" / "update-keys.json"
    ).read_bytes() == prepared.update_keys.read_bytes()
    assert (
        runtime / "release-trust" / "release-trust-inputs.json"
    ).read_bytes() == prepared.evidence.read_bytes()
    assert not (runtime / "release-trust" / "stray.txt").exists()
    assert not (runtime / "release-trust" / "stale.txt").exists()


def test_install_rejects_invalid_runtime_layout(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=tmp_path / "prepared",
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    with pytest.raises(ReleaseTrustInputError, match="runtime layout"):
        install_prepared_release_trust_inputs(runtime, prepared.directory)


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"schema_version": 2, "keys": [_key()]},
        {"schema_version": 1, "keys": []},
        {"schema_version": 1, "keys": [_key(), _key(), _key()]},
        {"schema_version": 1, "keys": ["not-an-object"]},
        {"schema_version": 1, "keys": [_key()], "extra": True},
        {
            "schema_version": 1,
            "keys": [{**_key(), "extra": True}],
        },
        {"schema_version": 1, "keys": [_key(key_id="Bad Key")]},
        {"schema_version": 1, "keys": [_key(algorithm="rsa")]},
        {
            "schema_version": 1,
            "keys": [_key(public_key=_RFC8032_PUBLIC_KEY.upper())],
        },
        {"schema_version": 1, "keys": [_key(state="retired")]},
        {
            "schema_version": 1,
            "keys": [
                _key(),
                _key(
                    key_id="release-2026-a",
                    public_key=_OTHER_PUBLIC_KEY,
                    state="next",
                ),
            ],
        },
        {
            "schema_version": 1,
            "keys": [
                _key(),
                _key(
                    key_id="release-2026-b",
                    public_key=_RFC8032_PUBLIC_KEY,
                    state="next",
                ),
            ],
        },
        {
            "schema_version": 1,
            "keys": [
                _key(state="next"),
                _key(
                    key_id="release-2026-b",
                    public_key=_OTHER_PUBLIC_KEY,
                    state="next",
                ),
            ],
        },
        {
            "schema_version": 1,
            "keys": [
                _key(),
                _key(
                    key_id="release-2026-b",
                    public_key=_OTHER_PUBLIC_KEY,
                    state="current",
                ),
            ],
        },
    ],
)
def test_update_key_catalog_rejects_invalid_shapes(document: object) -> None:
    payload = json.dumps(document).encode("utf-8")
    with pytest.raises(ReleaseTrustInputError):
        release_trust_inputs._parse_update_key_catalog(payload)


@pytest.mark.parametrize("payload", [b"\xff", b"{"])
def test_update_key_catalog_rejects_invalid_encoding(payload: bytes) -> None:
    with pytest.raises(ReleaseTrustInputError):
        release_trust_inputs._parse_update_key_catalog(payload)


def test_update_key_catalog_accepts_current_plus_next() -> None:
    document = _update_catalog(
        keys=[
            _key(),
            _key(
                key_id="release-2026-b",
                public_key=_OTHER_PUBLIC_KEY,
                state="next",
            ),
        ]
    )
    payload = json.dumps(document).encode("utf-8")

    assert release_trust_inputs._parse_update_key_catalog(payload) == (
        ("release-2026-a", "current"),
        ("release-2026-b", "next"),
    )


def test_prepare_rejects_invalid_model_catalog(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    model_path.write_text('{"schema_version":1,"models":[]}', encoding="utf-8")

    with pytest.raises(ReleaseTrustInputError, match="model trust catalog is invalid"):
        prepare_release_trust_inputs(
            update_key_catalog=update_path,
            model_trust_catalog=model_path,
            output_dir=tmp_path / "prepared",
        )


def test_prepared_evidence_detects_tampering(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=tmp_path / "prepared",
    )
    prepared.update_keys.write_bytes(prepared.update_keys.read_bytes() + b" ")

    with pytest.raises(
        ReleaseTrustInputError,
        match="prepared release trust bytes do not match their evidence",
    ):
        verify_prepared_release_trust_inputs(prepared.directory)


def test_prepared_evidence_must_be_valid_json(tmp_path: Path) -> None:
    update_path, model_path, _, _ = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update_path,
        model_trust_catalog=model_path,
        output_dir=tmp_path / "prepared",
    )
    prepared.evidence.write_text("{", encoding="utf-8")

    with pytest.raises(
        ReleaseTrustInputError,
        match="release trust evidence is unavailable or invalid",
    ):
        verify_prepared_release_trust_inputs(prepared.directory)


@pytest.mark.parametrize(
    "contents",
    [b"", b"x" * (32 * 1024 + 1)],
    ids=["empty", "oversized"],
)
def test_update_catalog_size_is_bounded(tmp_path: Path, contents: bytes) -> None:
    path = tmp_path / "update-keys.json"
    path.write_bytes(contents)

    with pytest.raises(ReleaseTrustInputError, match="bounded size"):
        release_trust_inputs._read_bounded(
            path,
            maximum=32 * 1024,
            label="update key catalog",
        )


def test_bounded_reader_rejects_directory_and_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ReleaseTrustInputError, match="regular file"):
        release_trust_inputs._read_bounded(
            tmp_path,
            maximum=32 * 1024,
            label="update key catalog",
        )
    with pytest.raises(ReleaseTrustInputError, match="unavailable"):
        release_trust_inputs._read_bounded(
            tmp_path / "missing.json",
            maximum=32 * 1024,
            label="update key catalog",
        )
