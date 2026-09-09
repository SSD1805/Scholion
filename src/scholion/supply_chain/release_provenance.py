from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from scholion.supply_chain.digests import sha256_file

_SCHEMA_VERSION = 1
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_TOOL_NAME_RE = re.compile(r"^[a-z0-9._-]{1,64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_TOOL_VALUE_LENGTH = 256


class ReleaseProvenanceError(ValueError):
    """Raised when release evidence cannot be bound to exact candidate bytes."""


def _require_bounded_text(value: object, field: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ReleaseProvenanceError(f"{field} must be bounded non-empty text")
    if any(character in value for character in ("\n", "\r", "\x00")):
        raise ReleaseProvenanceError(f"{field} must be one line")
    return value


def _require_sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ReleaseProvenanceError(f"{field} must be lowercase SHA-256 hex")
    return value


def _require_relative_path(value: object, field: str) -> PurePosixPath:
    text = _require_bounded_text(value, field, maximum=512)
    if "\\" in text:
        raise ReleaseProvenanceError(
            f"{field} must use repository-style forward slashes"
        )
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReleaseProvenanceError(f"{field} must be a normalized relative path")
    return path


def _resolve_beneath(root: Path, relative: PurePosixPath, field: str) -> Path:
    resolved_root = root.resolve(strict=True)
    candidate = (resolved_root / Path(*relative.parts)).resolve(strict=False)
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ReleaseProvenanceError(f"{field} escaped its approved root") from exc
    return candidate


def _load_qualification(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseProvenanceError(
            "qualification evidence is not readable JSON"
        ) from exc
    if not isinstance(document, dict):
        raise ReleaseProvenanceError("qualification evidence must be a JSON object")
    return document


def _measure_qualified_artifacts(
    qualification: Mapping[str, object],
    *,
    bundle_root: Path,
) -> list[dict[str, object]]:
    raw_artifacts = qualification.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ReleaseProvenanceError(
            "qualification evidence must identify package artifacts"
        )

    measured: list[dict[str, object]] = []
    seen_paths: set[str] = set()
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, dict):
            raise ReleaseProvenanceError(
                "qualification artifact entries must be objects"
            )
        relative = _require_relative_path(raw.get("path"), f"artifacts[{index}].path")
        relative_text = relative.as_posix()
        if relative_text in seen_paths:
            raise ReleaseProvenanceError("qualification artifact paths must be unique")
        seen_paths.add(relative_text)

        expected_size = raw.get("size_bytes")
        if (
            not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or expected_size < 1
        ):
            raise ReleaseProvenanceError("qualification artifact size must be positive")
        expected_digest = _require_sha256(
            raw.get("sha256"), f"artifacts[{index}].sha256"
        )

        artifact = _resolve_beneath(bundle_root, relative, f"artifacts[{index}].path")
        if not artifact.is_file():
            raise ReleaseProvenanceError("qualified artifact must be a regular file")
        actual_size = artifact.stat().st_size
        actual_digest = sha256_file(artifact)
        if actual_size != expected_size or actual_digest != expected_digest:
            raise ReleaseProvenanceError(
                "qualified artifact bytes no longer match qualification evidence"
            )
        measured.append(
            {
                "path": relative_text,
                "size_bytes": actual_size,
                "sha256": actual_digest,
            }
        )
    return sorted(measured, key=lambda item: str(item["path"]))


def _load_sha256sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseProvenanceError("SHA256SUMS is not readable") from exc
    if not lines:
        raise ReleaseProvenanceError("SHA256SUMS must not be empty")

    checksums: dict[str, str] = {}
    for index, line in enumerate(lines):
        if "  " not in line:
            raise ReleaseProvenanceError("SHA256SUMS has an invalid line")
        digest, raw_path = line.split("  ", 1)
        digest = _require_sha256(digest, f"SHA256SUMS[{index}].sha256")
        relative = _require_relative_path(raw_path, f"SHA256SUMS[{index}].path")
        relative_text = relative.as_posix()
        if relative_text in checksums:
            raise ReleaseProvenanceError("SHA256SUMS artifact paths must be unique")
        checksums[relative_text] = digest
    return checksums


def _cross_check_sha256sums(
    artifacts: Sequence[Mapping[str, object]],
    *,
    sha256sums_path: Path,
) -> None:
    checksums = _load_sha256sums(sha256sums_path)
    expected = {
        str(artifact["path"]): str(artifact["sha256"]) for artifact in artifacts
    }
    if checksums != expected:
        raise ReleaseProvenanceError(
            "SHA256SUMS does not describe the exact qualified artifact set"
        )


def _measure_inputs(
    repository_root: Path, inputs: Sequence[str]
) -> list[dict[str, str]]:
    if not inputs:
        raise ReleaseProvenanceError(
            "release provenance requires repository input identities"
        )
    measured: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(inputs):
        relative = _require_relative_path(value, f"inputs[{index}]")
        relative_text = relative.as_posix()
        if relative_text in seen:
            raise ReleaseProvenanceError("release provenance inputs must be unique")
        seen.add(relative_text)
        candidate = _resolve_beneath(repository_root, relative, f"inputs[{index}]")
        if not candidate.is_file():
            raise ReleaseProvenanceError(
                "release provenance inputs must be regular files"
            )
        measured.append({"path": relative_text, "sha256": sha256_file(candidate)})
    return sorted(measured, key=lambda item: item["path"])


def _validate_toolchain(toolchain: Mapping[str, str]) -> dict[str, str]:
    if not toolchain:
        raise ReleaseProvenanceError("release provenance requires toolchain identity")
    normalized: dict[str, str] = {}
    for name, raw_value in toolchain.items():
        if _TOOL_NAME_RE.fullmatch(name) is None:
            raise ReleaseProvenanceError("toolchain names must be bounded identifiers")
        value = _require_bounded_text(
            raw_value,
            f"toolchain.{name}",
            maximum=_MAX_TOOL_VALUE_LENGTH,
        )
        normalized[name] = value
    return dict(sorted(normalized.items()))


def build_release_provenance(
    *,
    repository_root: Path,
    qualification_path: Path,
    sha256sums_path: Path,
    bundle_root: Path,
    commit: str,
    runner_os: str,
    runner_arch: str,
    inputs: Sequence[str],
    toolchain: Mapping[str, str],
) -> bytes:
    """Bind exact qualified package bytes to reviewed repository/build inputs."""
    if _COMMIT_RE.fullmatch(commit) is None:
        raise ReleaseProvenanceError("commit must be a lowercase 40-hex Git SHA")
    runner_os = _require_bounded_text(runner_os, "runner_os", maximum=64)
    runner_arch = _require_bounded_text(runner_arch, "runner_arch", maximum=64)

    qualification_path = qualification_path.resolve(strict=True)
    sha256sums_path = sha256sums_path.resolve(strict=True)
    qualification = _load_qualification(qualification_path)
    if qualification.get("schema_version") != 1:
        raise ReleaseProvenanceError("unsupported qualification evidence schema")
    if qualification.get("commit") != commit:
        raise ReleaseProvenanceError(
            "qualification commit does not match provenance commit"
        )
    if qualification.get("runner_os") != runner_os:
        raise ReleaseProvenanceError(
            "qualification runner OS does not match provenance runner"
        )
    if qualification.get("release_ready") is not False:
        raise ReleaseProvenanceError(
            "preview provenance must not relabel an artifact release-ready"
        )

    artifacts = _measure_qualified_artifacts(
        qualification,
        bundle_root=bundle_root,
    )
    _cross_check_sha256sums(artifacts, sha256sums_path=sha256sums_path)

    document = {
        "schema_version": _SCHEMA_VERSION,
        "qualification": _require_bounded_text(
            qualification.get("qualification"), "qualification", maximum=64
        ),
        "commit": commit,
        "runner": {"os": runner_os, "arch": runner_arch},
        "qualification_sha256": sha256_file(qualification_path),
        "sha256sums_sha256": sha256_file(sha256sums_path),
        "artifacts": artifacts,
        "inputs": _measure_inputs(repository_root, inputs),
        "toolchain": _validate_toolchain(toolchain),
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _command_version(*command: str) -> str:
    # All callers supply repository-owned fixed executable names and arguments. This
    # stays no-shell and captures only bounded version output for provenance.
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseProvenanceError(
            f"could not resolve build tool version for {command[0]}"
        ) from exc
    output = (completed.stdout or completed.stderr).strip()
    return _require_bounded_text(
        output, f"toolchain.{command[0]}", maximum=_MAX_TOOL_VALUE_LENGTH
    )


def collect_release_toolchain(repository_root: Path) -> dict[str, str]:
    """Capture only bounded version identity for tools that built the candidate."""
    tauri_package = (
        repository_root
        / "frontend"
        / "node_modules"
        / "@tauri-apps"
        / "cli"
        / "package.json"
    )
    try:
        tauri_document = json.loads(tauri_package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseProvenanceError(
            "could not resolve installed Tauri CLI identity"
        ) from exc
    tauri_version = (
        tauri_document.get("version") if isinstance(tauri_document, dict) else None
    )
    npm_executable = "npm.cmd" if platform.system() == "Windows" else "npm"

    return _validate_toolchain(
        {
            "python": platform.python_version(),
            "uv": _command_version("uv", "--version"),
            "pyinstaller": importlib.metadata.version("pyinstaller"),
            "node": _command_version("node", "--version"),
            "npm": _command_version(npm_executable, "--version"),
            "rustc": _command_version("rustc", "--version"),
            "cargo": _command_version("cargo", "--version"),
            "tauri-cli": _require_bounded_text(
                tauri_version,
                "toolchain.tauri-cli",
                maximum=64,
            ),
        }
    )
