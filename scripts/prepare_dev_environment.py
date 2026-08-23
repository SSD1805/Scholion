from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _project_uv(repo_root: Path) -> Path:
    tools_root = repo_root / ".tools" / "uv"
    if os.name == "nt":
        return tools_root / "Scripts" / "uv.exe"
    return tools_root / "bin" / "uv"


def _run(*args: str, cwd: Path) -> None:
    # Executables and arguments are repository-controlled paths or fixed literals.
    # No shell is involved and no user-provided command is executed.
    subprocess.run(args, cwd=cwd, check=True)  # noqa: S603


def _ensure_project_uv(repo_root: Path) -> Path:
    uv = _project_uv(repo_root)
    if uv.is_file():
        return uv

    bootstrap = repo_root / "scripts" / "bootstrap_python.py"
    if not bootstrap.is_file():
        raise SystemExit(
            "Scholion checkout is incomplete; missing: bootstrap_python.py"
        )

    if sys.version_info[:2] != (3, 12):
        raise SystemExit(
            "Scholion requires Python 3.12 for source development. "
            "Run this script with Python 3.12 so it can create the project-local toolchain."
        )

    print("Project-local uv is missing; bootstrapping it inside .tools/uv")
    _run(sys.executable, str(bootstrap), cwd=repo_root)
    if not uv.is_file():
        raise SystemExit(
            "Project-local uv bootstrap completed without creating .tools/uv"
        )
    return uv


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    required = (repo_root / "pyproject.toml", repo_root / "uv.lock")
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Scholion checkout is incomplete; missing: {names}")

    uv = _ensure_project_uv(repo_root)

    _run(
        str(uv),
        "sync",
        "--locked",
        "--all-groups",
        "--extra",
        "transcription",
        cwd=repo_root,
    )
    _run(
        str(uv),
        "run",
        "poodle",
        "--help",
        cwd=repo_root,
    )
    print("Scholion development environment ready; Poodle is available.")
    print(f"Using project-local uv: {uv}")
    print("No system-wide uv installation is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
