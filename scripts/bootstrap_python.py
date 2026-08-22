from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

UV_VERSION = "0.11.33"


def run(*args: str, cwd: Path | None = None) -> None:
    # Every executable/argument is constructed from repository-controlled paths and
    # fixed literals; no shell is involved and no user-provided command is executed.
    subprocess.run(args, cwd=cwd, check=True)  # noqa: S603


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    tools_root = repo_root / ".tools" / "uv"
    tools_python = (
        tools_root / "Scripts" / "python.exe"
        if os.name == "nt"
        else tools_root / "bin" / "python"
    )
    uv_executable = (
        tools_root / "Scripts" / "uv.exe"
        if os.name == "nt"
        else tools_root / "bin" / "uv"
    )

    if sys.version_info[:2] != (3, 12):
        print(
            "Scholion requires Python 3.12 for source development. "
            f"This bootstrap is running under {sys.version.split()[0]}.",
            file=sys.stderr,
        )
        return 2

    if not tools_python.exists():
        print(f"Creating project-local uv tool environment at {tools_root}")
        run(sys.executable, "-m", "venv", str(tools_root))

    print(f"Ensuring uv {UV_VERSION} is installed only inside .tools/uv")
    run(
        str(tools_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        f"uv=={UV_VERSION}",
    )

    print("Synchronizing Scholion's locked Python environment")
    run(
        str(uv_executable),
        "sync",
        "--locked",
        "--extra",
        "transcription",
        cwd=repo_root,
    )

    project_python = (
        repo_root / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else repo_root / ".venv" / "bin" / "python"
    )
    if not project_python.exists():
        print("Bootstrap completed without creating .venv/bin/python", file=sys.stderr)
        return 3

    run(str(project_python), "-c", "import scholion; print('Scholion import OK')")
    print()
    print("Project-local toolchain is ready:")
    print(f"  uv tool: {uv_executable}")
    print(f"  project Python: {project_python}")
    print("No system-wide uv installation was required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
