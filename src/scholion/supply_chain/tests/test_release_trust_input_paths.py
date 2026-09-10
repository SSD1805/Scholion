from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scholion.supply_chain import release_trust_inputs
from scholion.supply_chain.release_trust_inputs import (
    ReleaseTrustInputError,
    install_prepared_release_trust_inputs,
    prepare_release_trust_inputs,
    verify_prepared_release_trust_inputs,
)

_PUBLIC_KEY = "01" * 32


def _write_inputs(root: Path) -> tuple[Path, Path]:
    update = root / "source-update-keys.json"
    update.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "keys": [
                    {
                        "key_id": "release-2026-a",
                        "algorithm": "ed25519",
                        "public_key_hex": _PUBLIC_KEY,
                        "state": "current",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    model = root / "source-model-trust.json"
    model.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    return update, model


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation is not reliable in CI")
def test_prepare_unlinks_preexisting_output_symlink(tmp_path: Path) -> None:
    update, model = _write_inputs(tmp_path)
    output = tmp_path / "prepared"
    output.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("do not overwrite", encoding="utf-8")
    (output / "update-keys.json").symlink_to(outside)

    prepared = prepare_release_trust_inputs(
        update_key_catalog=update,
        model_trust_catalog=model,
        output_dir=output,
    )

    assert outside.read_text(encoding="utf-8") == "do not overwrite"
    assert not prepared.update_keys.is_symlink()
    assert prepared.update_keys.read_bytes() == update.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation is not reliable in CI")
def test_prepared_verifier_rejects_input_symlink(tmp_path: Path) -> None:
    update, model = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update,
        model_trust_catalog=model,
        output_dir=tmp_path / "prepared",
    )
    copied = tmp_path / "copied-update.json"
    copied.write_bytes(prepared.update_keys.read_bytes())
    prepared.update_keys.unlink()
    prepared.update_keys.symlink_to(copied)

    with pytest.raises(ReleaseTrustInputError, match="must not be a symlink"):
        verify_prepared_release_trust_inputs(prepared.directory)


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation is not reliable in CI")
def test_install_rejects_model_destination_parent_escape(tmp_path: Path) -> None:
    update, model = _write_inputs(tmp_path)
    prepared = prepare_release_trust_inputs(
        update_key_catalog=update,
        model_trust_catalog=model,
        output_dir=tmp_path / "prepared",
    )
    runtime = tmp_path / "runtime"
    internal = runtime / "_internal"
    internal.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (internal / "scholion").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ReleaseTrustInputError, match="escaped the runtime"):
        install_prepared_release_trust_inputs(runtime, prepared.directory)

    assert not (outside / "supply_chain" / "model-trust.json").exists()


def test_output_path_rejects_directory_collision(tmp_path: Path) -> None:
    output = tmp_path / "prepared"
    output.mkdir()
    (output / "update-keys.json").mkdir()

    with pytest.raises(ReleaseTrustInputError, match="not a regular file"):
        release_trust_inputs._output_file(output, "update-keys.json")
