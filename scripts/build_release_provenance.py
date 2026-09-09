from __future__ import annotations

import argparse
from pathlib import Path

from scholion.supply_chain.release_provenance import (
    build_release_provenance,
    collect_release_toolchain,
)

_DEFAULT_INPUTS = (
    "uv.lock",
    "frontend/package-lock.json",
    "frontend/src-tauri/Cargo.lock",
    "frontend/src-tauri/tauri.release.conf.json",
    "frontend/src-tauri/icons/scholion-master.svg",
    "packaging/media-tools.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic provenance for an exact qualified Scholion package."
        )
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--sha256sums", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--runner-os", required=True)
    parser.add_argument("--runner-arch", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    repository_root = arguments.repository_root.resolve(strict=True)
    payload = build_release_provenance(
        repository_root=repository_root,
        qualification_path=arguments.qualification,
        sha256sums_path=arguments.sha256sums,
        bundle_root=arguments.bundle_root,
        commit=arguments.commit,
        runner_os=arguments.runner_os,
        runner_arch=arguments.runner_arch,
        inputs=_DEFAULT_INPUTS,
        toolchain=collect_release_toolchain(repository_root),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
