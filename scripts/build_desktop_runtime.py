from __future__ import annotations

import argparse
import importlib.metadata
import shutil
import sys
import tempfile
from pathlib import Path

_EXPECTED_PYINSTALLER = "6.22.2"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _runtime_executable(runtime_dir: Path) -> Path:
    name = "scholion-runtime.exe" if sys.platform == "win32" else "scholion-runtime"
    return runtime_dir / name


def build_runtime(output_dir: Path) -> Path:
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
            [
                "--noconfirm",
                "--clean",
                "--onedir",
                "--name",
                "scholion-runtime",
                "--paths",
                str(root / "src"),
                "--collect-submodules",
                "scholion",
                "--collect-all",
                "faster_whisper",
                "--collect-all",
                "ctranslate2",
                "--collect-all",
                "duckdb",
                "--collect-all",
                "lingua",
                "--distpath",
                str(dist_path),
                "--workpath",
                str(work_path),
                "--specpath",
                str(spec_path),
                str(root / "scripts" / "scholion_runtime_entry.py"),
            ]
        )
        built = dist_path / "scholion-runtime"
        if not built.is_dir():
            raise RuntimeError("PyInstaller did not produce the expected runtime directory")
        shutil.copytree(built, staging_dir)

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
    arguments = parser.parse_args()
    executable = build_runtime(arguments.output_dir)
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
