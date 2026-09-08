import json
from pathlib import Path

import pytest

from scholion.supply_chain.digests import sha256_file
from scholion.supply_chain.release_provenance import (
    ReleaseProvenanceError,
    build_release_provenance,
)

_COMMIT = "a" * 40
_RUNNER_OS = "Windows"
_RUNNER_ARCH = "X64"
_TOOLCHAIN = {
    "cargo": "cargo 1.90.0",
    "node": "v24.0.0",
    "pyinstaller": "6.22.2",
}


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    (root / "frontend" / "src-tauri" / "icons").mkdir(parents=True)
    (root / "frontend" / "src-tauri" / "Cargo.lock").write_text("cargo\n")
    (root / "frontend" / "src-tauri" / "tauri.release.conf.json").write_text(
        "{}\n"
    )
    (root / "frontend" / "src-tauri" / "icons" / "scholion-master.svg").write_text(
        "<svg/>\n"
    )
    (root / "frontend" / "package-lock.json").write_text("{}\n")
    (root / "uv.lock").write_text("uv\n")
    return root


def _qualified_preview(
    tmp_path: Path,
    *,
    commit: str = _COMMIT,
    runner_os: str = _RUNNER_OS,
    release_ready: bool = False,
) -> tuple[Path, Path]:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    artifact = bundle_root / "nsis" / "Scholion.exe"
    artifact.parent.mkdir()
    artifact.write_bytes(b"exact-package-bytes")

    evidence = tmp_path / "release-preview" / "qualification.json"
    evidence.parent.mkdir()
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "qualification": "unsigned-preview",
                "commit": commit,
                "runner_os": runner_os,
                "release_ready": release_ready,
                "artifacts": [
                    {
                        "path": "nsis/Scholion.exe",
                        "size_bytes": artifact.stat().st_size,
                        "sha256": sha256_file(artifact),
                    }
                ],
            }
        )
    )
    return bundle_root, evidence


def _inputs() -> tuple[str, ...]:
    return (
        "uv.lock",
        "frontend/package-lock.json",
        "frontend/src-tauri/Cargo.lock",
        "frontend/src-tauri/tauri.release.conf.json",
        "frontend/src-tauri/icons/scholion-master.svg",
    )


def test_provenance_is_deterministic_and_binds_exact_evidence(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path)

    first = build_release_provenance(
        repository_root=repository,
        qualification_path=qualification,
        bundle_root=bundle_root,
        commit=_COMMIT,
        runner_os=_RUNNER_OS,
        runner_arch=_RUNNER_ARCH,
        inputs=_inputs(),
        toolchain=_TOOLCHAIN,
    )
    second = build_release_provenance(
        repository_root=repository,
        qualification_path=qualification,
        bundle_root=bundle_root,
        commit=_COMMIT,
        runner_os=_RUNNER_OS,
        runner_arch=_RUNNER_ARCH,
        inputs=tuple(reversed(_inputs())),
        toolchain=dict(reversed(tuple(_TOOLCHAIN.items()))),
    )

    assert first == second
    document = json.loads(first)
    assert document["commit"] == _COMMIT
    assert document["runner"] == {"arch": _RUNNER_ARCH, "os": _RUNNER_OS}
    assert document["qualification_sha256"] == sha256_file(qualification)
    assert document["artifacts"][0]["path"] == "nsis/Scholion.exe"
    assert document["artifacts"][0]["sha256"] == sha256_file(
        bundle_root / "nsis" / "Scholion.exe"
    )
    assert [item["path"] for item in document["inputs"]] == sorted(_inputs())


def test_provenance_rejects_mutated_package_after_qualification(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path)
    (bundle_root / "nsis" / "Scholion.exe").write_bytes(b"different")

    with pytest.raises(ReleaseProvenanceError, match="no longer match"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_provenance_rejects_qualification_commit_mismatch(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path, commit="b" * 40)

    with pytest.raises(ReleaseProvenanceError, match="commit does not match"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_provenance_rejects_qualification_runner_mismatch(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path, runner_os="macOS")

    with pytest.raises(ReleaseProvenanceError, match="runner OS does not match"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_preview_provenance_cannot_relabel_release_ready_artifact(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path, release_ready=True)

    with pytest.raises(ReleaseProvenanceError, match="must not relabel"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_provenance_rejects_package_path_escape(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path)
    document = json.loads(qualification.read_text())
    document["artifacts"][0]["path"] = "../outside.bin"
    qualification.write_text(json.dumps(document))

    with pytest.raises(ReleaseProvenanceError, match="normalized relative path"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_provenance_rejects_malformed_qualification_digest(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path)
    document = json.loads(qualification.read_text())
    document["artifacts"][0]["sha256"] = "nope"
    qualification.write_text(json.dumps(document))

    with pytest.raises(ReleaseProvenanceError, match="lowercase SHA-256"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=_inputs(),
            toolchain=_TOOLCHAIN,
        )


def test_provenance_rejects_duplicate_repository_inputs(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    bundle_root, qualification = _qualified_preview(tmp_path)

    with pytest.raises(ReleaseProvenanceError, match="inputs must be unique"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os=_RUNNER_OS,
            runner_arch=_RUNNER_ARCH,
            inputs=("uv.lock", "uv.lock"),
            toolchain=_TOOLCHAIN,
        )
