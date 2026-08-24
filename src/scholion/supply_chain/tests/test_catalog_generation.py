from pathlib import Path

import pytest

from scholion.supply_chain.catalog_generation import generate_trusted_model_spec

_REVISION = "a" * 40


def _generate(snapshot: Path, cache: Path):
    return generate_trusted_model_spec(
        model_id="tiny",
        engine="faster-whisper",
        repository_id="Systran/faster-whisper-tiny",
        revision=_REVISION,
        source_url="https://huggingface.co/Systran/faster-whisper-tiny",
        license_id="mit",
        license_url="https://example.test/license",
        snapshot_root=snapshot,
        cache_root=cache,
    )


def test_generator_records_sorted_exact_files_sizes_and_hashes(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "repo" / "snapshots" / _REVISION
    snapshot.mkdir(parents=True)
    (snapshot / "z.bin").write_bytes(b"z")
    (snapshot / "a.json").write_bytes(b"{}")

    spec = _generate(snapshot, cache)

    assert tuple(item.path for item in spec.files) == ("a.json", "z.bin")
    assert tuple(item.size_bytes for item in spec.files) == (2, 1)
    assert all(len(item.sha256_hex) == 64 for item in spec.files)
    assert spec.revision == _REVISION


def test_generator_requires_snapshot_directory_to_equal_reviewed_revision(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "repo" / "snapshots" / "main"
    snapshot.mkdir(parents=True)
    (snapshot / "model.bin").write_bytes(b"model")

    with pytest.raises(ValueError, match="immutable revision"):
        _generate(snapshot, cache)


def test_generator_rejects_empty_snapshot(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "repo" / "snapshots" / _REVISION
    snapshot.mkdir(parents=True)

    with pytest.raises(ValueError, match="contains no files"):
        _generate(snapshot, cache)


def test_generator_rejects_file_symlink_that_escapes_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "repo" / "snapshots" / _REVISION
    snapshot.mkdir(parents=True)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    link = snapshot / "model.bin"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable on this test platform")

    with pytest.raises(ValueError, match="outside the supplied cache root"):
        _generate(snapshot, cache)


def test_generator_allows_huggingface_style_symlink_within_cache(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "cache"
    snapshot = cache / "repo" / "snapshots" / _REVISION
    blobs = cache / "repo" / "blobs"
    snapshot.mkdir(parents=True)
    blobs.mkdir(parents=True)
    blob = blobs / "abc"
    blob.write_bytes(b"model")
    link = snapshot / "model.bin"
    try:
        link.symlink_to(blob)
    except OSError:
        pytest.skip("symlinks are unavailable on this test platform")

    spec = _generate(snapshot, cache)

    assert spec.files[0].path == "model.bin"
    assert spec.files[0].size_bytes == 5
