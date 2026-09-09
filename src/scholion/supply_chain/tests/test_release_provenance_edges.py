import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scholion.supply_chain.digests import sha256_file
from scholion.supply_chain.release_provenance import (
    ReleaseProvenanceError,
    build_release_provenance,
    collect_release_toolchain,
)

_COMMIT = "a" * 40


def _setup(tmp_path: Path) -> tuple[Path, Path, Path, Path, tuple[str, ...]]:
    repository = tmp_path / "repository"
    (repository / "frontend" / "src-tauri" / "icons").mkdir(parents=True, exist_ok=True)
    files = {
        "uv.lock": "uv\n",
        "frontend/package-lock.json": "{}\n",
        "frontend/src-tauri/Cargo.lock": "cargo\n",
        "frontend/src-tauri/tauri.release.conf.json": "{}\n",
        "frontend/src-tauri/icons/scholion-master.svg": "<svg/>\n",
    }
    for relative, content in files.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    bundle_root = tmp_path / "bundle"
    artifact = bundle_root / "nsis" / "Scholion.exe"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"package")
    digest = sha256_file(artifact)

    evidence_dir = tmp_path / "release-preview"
    evidence_dir.mkdir(exist_ok=True)
    qualification = evidence_dir / "qualification.json"
    qualification.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "qualification": "unsigned-preview",
                "commit": _COMMIT,
                "runner_os": "Windows",
                "release_ready": False,
                "artifacts": [
                    {
                        "path": "nsis/Scholion.exe",
                        "size_bytes": artifact.stat().st_size,
                        "sha256": digest,
                    }
                ],
            }
        )
    )
    sha256sums = evidence_dir / "SHA256SUMS"
    sha256sums.write_text(f"{digest}  nsis/Scholion.exe\n")
    return repository, bundle_root, qualification, sha256sums, tuple(files)


def _build(
    tmp_path: Path,
    *,
    commit: str = _COMMIT,
    inputs: tuple[str, ...] | None = None,
    toolchain: dict[str, str] | None = None,
) -> bytes:
    repository, bundle_root, qualification, sha256sums, default_inputs = _setup(
        tmp_path
    )
    return build_release_provenance(
        repository_root=repository,
        qualification_path=qualification,
        sha256sums_path=sha256sums,
        bundle_root=bundle_root,
        commit=commit,
        runner_os="Windows",
        runner_arch="X64",
        inputs=default_inputs if inputs is None else inputs,
        toolchain={"python": "3.12.14"} if toolchain is None else toolchain,
    )


@pytest.mark.parametrize("commit", ["short", "A" * 40])
def test_provenance_rejects_invalid_commit_identity(
    tmp_path: Path, commit: str
) -> None:
    with pytest.raises(ReleaseProvenanceError, match="40-hex"):
        _build(tmp_path, commit=commit)


def test_provenance_rejects_unreadable_qualification_json(tmp_path: Path) -> None:
    repository, bundle_root, qualification, sha256sums, inputs = _setup(tmp_path)
    qualification.write_text("{")

    with pytest.raises(ReleaseProvenanceError, match="not readable JSON"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )


def test_provenance_rejects_non_object_qualification(tmp_path: Path) -> None:
    repository, bundle_root, qualification, sha256sums, inputs = _setup(tmp_path)
    qualification.write_text("[]")

    with pytest.raises(ReleaseProvenanceError, match="JSON object"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )


def test_provenance_rejects_invalid_artifact_entry_and_size(tmp_path: Path) -> None:
    repository, bundle_root, qualification, sha256sums, inputs = _setup(tmp_path)
    document = json.loads(qualification.read_text())
    document["artifacts"] = ["not-an-object"]
    qualification.write_text(json.dumps(document))

    with pytest.raises(ReleaseProvenanceError, match="entries must be objects"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )

    document["artifacts"] = [
        {
            "path": "nsis/Scholion.exe",
            "size_bytes": 0,
            "sha256": sha256_file(bundle_root / "nsis" / "Scholion.exe"),
        }
    ]
    qualification.write_text(json.dumps(document))
    with pytest.raises(ReleaseProvenanceError, match="size must be positive"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )


def test_provenance_rejects_duplicate_artifact_paths(tmp_path: Path) -> None:
    repository, bundle_root, qualification, sha256sums, inputs = _setup(tmp_path)
    document = json.loads(qualification.read_text())
    document["artifacts"].append(dict(document["artifacts"][0]))
    qualification.write_text(json.dumps(document))

    with pytest.raises(ReleaseProvenanceError, match="paths must be unique"):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )


@pytest.mark.parametrize(
    ("contents", "match"),
    [
        ("", "must not be empty"),
        ("not-a-checksum-line\n", "invalid line"),
        (f"{'x' * 64}  nsis/Scholion.exe\n", "lowercase SHA-256"),
    ],
)
def test_provenance_rejects_malformed_checksum_evidence(
    tmp_path: Path, contents: str, match: str
) -> None:
    repository, bundle_root, qualification, sha256sums, inputs = _setup(tmp_path)
    sha256sums.write_text(contents)

    with pytest.raises(ReleaseProvenanceError, match=match):
        build_release_provenance(
            repository_root=repository,
            qualification_path=qualification,
            sha256sums_path=sha256sums,
            bundle_root=bundle_root,
            commit=_COMMIT,
            runner_os="Windows",
            runner_arch="X64",
            inputs=inputs,
            toolchain={"python": "3.12"},
        )


def test_provenance_rejects_missing_and_unsafe_repository_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ReleaseProvenanceError, match="requires repository input"):
        _build(tmp_path, inputs=())

    with pytest.raises(ReleaseProvenanceError, match="forward slashes"):
        _build(tmp_path, inputs=("frontend\\package-lock.json",))

    with pytest.raises(ReleaseProvenanceError, match="regular files"):
        _build(tmp_path, inputs=("missing.lock",))


def test_provenance_rejects_invalid_toolchain_identity(tmp_path: Path) -> None:
    with pytest.raises(ReleaseProvenanceError, match="requires toolchain identity"):
        _build(tmp_path, toolchain={})

    with pytest.raises(ReleaseProvenanceError, match="bounded identifiers"):
        _build(tmp_path, toolchain={"Not Valid": "1"})

    with pytest.raises(ReleaseProvenanceError, match="one line"):
        _build(tmp_path, toolchain={"python": "3.12\nextra"})


def test_collect_release_toolchain_uses_windows_npm_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    tauri_package = (
        repository
        / "frontend"
        / "node_modules"
        / "@tauri-apps"
        / "cli"
        / "package.json"
    )
    tauri_package.parent.mkdir(parents=True)
    tauri_package.write_text(json.dumps({"version": "2.8.5"}))

    versions = {
        "uv": "uv 0.11.33",
        "node": "v24.8.0",
        "npm.cmd": "11.6.0",
        "rustc": "rustc 1.90.0",
        "cargo": "cargo 1.90.0",
    }

    def fake_run(command: tuple[str, ...], **_: object) -> SimpleNamespace:
        return SimpleNamespace(stdout=versions[command[0]], stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("importlib.metadata.version", lambda _: "6.22.2")
    monkeypatch.setattr(
        "scholion.supply_chain.release_provenance.platform.system",
        lambda: "Windows",
    )

    toolchain = collect_release_toolchain(repository)

    assert toolchain["tauri-cli"] == "2.8.5"
    assert toolchain["pyinstaller"] == "6.22.2"
    assert toolchain["uv"] == "uv 0.11.33"
    assert toolchain["npm"] == "11.6.0"
    assert toolchain["cargo"] == "cargo 1.90.0"


def test_collect_release_toolchain_fails_closed_on_missing_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    tauri_package = (
        repository
        / "frontend"
        / "node_modules"
        / "@tauri-apps"
        / "cli"
        / "package.json"
    )
    tauri_package.parent.mkdir(parents=True)
    tauri_package.write_text(json.dumps({"version": "2.8.5"}))

    def fail_run(*_: object, **__: object) -> None:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(subprocess, "run", fail_run)
    monkeypatch.setattr("importlib.metadata.version", lambda _: "6.22.2")

    with pytest.raises(ReleaseProvenanceError, match="could not resolve build tool"):
        collect_release_toolchain(repository)
