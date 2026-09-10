from __future__ import annotations

import argparse
import importlib.metadata
import shutil
import sys
import tempfile
from pathlib import Path

from scholion.supply_chain.release_trust_inputs import (
    verify_prepared_release_trust_inputs,
)

_EXPECTED_PYINSTALLER = "6.22.2"
_RUNTIME_METADATA = (
    "scholion",
    "faster-whisper",
    "ctranslate2",
    "duckdb",
    "lingua-language-detector",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runtime_executable(runtime_dir: Path) -> Path:
    name = "scholion-runtime.exe" if sys.platform == "win32" else "scholion-runtime"
    return runtime_dir / name


def _managed_media_files(media_tools_dir: Path) -> tuple[Path, Path, Path]:
    suffix = ".exe" if sys.platform == "win32" else ""
    ffmpeg = media_tools_dir / f"ffmpeg{suffix}"
    ffprobe = media_tools_dir / f"ffprobe{suffix}"
    evidence = media_tools_dir / "managed-media-tools.json"
    for path in (ffmpeg, ffprobe, evidence):
        if not path.is_file():
            raise RuntimeError(f"Managed media-tool input is missing: {path.name}")
    return ffmpeg, ffprobe, evidence


def _overlay_managed_media_files(runtime_dir: Path, media_tools_dir: Path) -> None:
    """Copy reviewed media bytes after PyInstaller finishes touching Mach-O binaries."""
    inputs = _managed_media_files(media_tools_dir)
    internal = runtime_dir / "_internal"
    if not internal.is_dir():
        raise RuntimeError("PyInstaller runtime internal directory is missing")
    destination = internal / "media-tools"
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir()
    for source in inputs:
        shutil.copy2(source, destination / source.name)


def _overlay_release_trust_files(runtime_dir: Path, trust_inputs_dir: Path) -> None:
    """Copy reviewed trust bytes only after their preparation evidence re-verifies."""
    prepared = verify_prepared_release_trust_inputs(trust_inputs_dir)
    internal = runtime_dir / "_internal"
    if not internal.is_dir():
        raise RuntimeError("PyInstaller runtime internal directory is missing")

    model_destination = internal / "scholion" / "supply_chain" / "model-trust.json"
    model_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prepared.model_trust, model_destination)

    public_destination = runtime_dir / "release-trust"
    shutil.rmtree(public_destination, ignore_errors=True)
    public_destination.mkdir()
    shutil.copy2(prepared.update_keys, public_destination / prepared.update_keys.name)
    shutil.copy2(prepared.evidence, public_destination / prepared.evidence.name)


def _pyinstaller_arguments(
    root: Path,
    dist_path: Path,
    work_path: Path,
    spec_path: Path,
) -> list[str]:
    arguments = [
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "scholion-runtime",
        "--paths",
        str(root / "src"),
        # dependency-injector uses Cython extension modules whose imports are not all
        # visible to PyInstaller's static graph. Collect that package explicitly so a
        # frozen AppContainer has the same module surface as the locked Python graph.
        "--collect-submodules",
        "dependency_injector",
        "--collect-all",
        "faster_whisper",
        "--collect-all",
        "ctranslate2",
        "--collect-all",
        "duckdb",
        "--collect-all",
        "lingua",
    ]
    for distribution in _RUNTIME_METADATA:
        arguments.extend(("--copy-metadata", distribution))
    arguments.extend(
        (
            "--distpath",
            str(dist_path),
            "--workpath",
            str(work_path),
            "--specpath",
            str(spec_path),
            str(root / "scripts" / "scholion_runtime_entry.py"),
        )
    )
    return arguments


def build_runtime(
    output_dir: Path,
    media_tools_dir: Path,
    release_trust_dir: Path | None = None,
) -> Path:
    try:
        pyinstaller_version = importlib.metadata.version("pyinstaller")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "PyInstaller is required; install Scholion's packaging dependency group"
        ) from exc
    if pyinstaller_version != _EXPECTED_PYINSTALLER:
        raise RuntimeError(
            f"Expected PyInstaller {_EXPECTED_PYINSTALLER}, found {pyinstaller_version}"
        )

    from PyInstaller.__main__ import run as pyinstaller_run

    root = _repository_root()
    output_dir = output_dir.resolve()
    media_tools_dir = media_tools_dir.resolve(strict=True)
    _managed_media_files(media_tools_dir)
    if release_trust_dir is not None:
        release_trust_dir = release_trust_dir.resolve(strict=True)
        verify_prepared_release_trust_inputs(release_trust_dir)
    staging_dir = output_dir.parent / ".runtime-build"
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)

    with tempfile.TemporaryDirectory(prefix="scholion-pyinstaller-") as temporary:
        temporary_path = Path(temporary)
        dist_path = temporary_path / "dist"
        work_path = temporary_path / "work"
        spec_path = temporary_path / "spec"
        pyinstaller_run(
            _pyinstaller_arguments(
                root,
                dist_path,
                work_path,
                spec_path,
            )
        )
        built = dist_path / "scholion-runtime"
        if not built.is_dir():
            raise RuntimeError(
                "PyInstaller did not produce the expected runtime directory"
            )
        shutil.copytree(built, staging_dir)
        _overlay_managed_media_files(staging_dir, media_tools_dir)
        if release_trust_dir is not None:
            _overlay_release_trust_files(staging_dir, release_trust_dir)

    staging_dir.replace(output_dir)
    executable = _runtime_executable(output_dir)
    if not executable.is_file():
        raise RuntimeError("Packaged Scholion runtime executable is missing")
    return executable


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the closed Scholion desktop Python runtime directory."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_repository_root() / "frontend" / "src-tauri" / "resources" / "runtime",
    )
    parser.add_argument(
        "--media-tools-dir",
        type=Path,
        default=_repository_root() / "build" / "managed-media-tools",
    )
    parser.add_argument(
        "--release-trust-dir",
        type=Path,
        help=(
            "Prepared release trust directory. Omit it for trust-free preview/source "
            "builds that must keep updates disabled."
        ),
    )
    arguments = parser.parse_args()
    executable = build_runtime(
        arguments.output_dir,
        arguments.media_tools_dir,
        arguments.release_trust_dir,
    )
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
