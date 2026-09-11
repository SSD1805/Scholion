#!/usr/bin/env python3
"""Verify exact prepared release trust bytes inside one frozen Scholion runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

from scholion.supply_chain.release_trust_inputs import (
    verify_prepared_release_trust_inputs,
)


def verify(runtime: Path, prepared_dir: Path) -> None:
    executable = runtime.expanduser().resolve(strict=True)
    if not executable.is_file():
        raise RuntimeError("packaged Scholion runtime executable is missing")
    runtime_dir = executable.parent
    prepared = verify_prepared_release_trust_inputs(prepared_dir)

    expected = {
        runtime_dir
        / "_internal"
        / "scholion"
        / "supply_chain"
        / "model-trust.json": prepared.model_trust,
        runtime_dir / "release-trust" / "update-keys.json": prepared.update_keys,
        runtime_dir / "release-trust" / "release-trust-inputs.json": prepared.evidence,
    }
    for packaged, source in expected.items():
        try:
            packaged_payload = packaged.read_bytes()
            source_payload = source.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                "packaged release trust input is missing or unreadable"
            ) from exc
        if packaged_payload != source_payload:
            raise RuntimeError(
                "packaged release trust input does not match prepared review evidence"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove exact reviewed trust bytes inside a frozen Scholion runtime."
    )
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--prepared-dir", required=True, type=Path)
    arguments = parser.parse_args()
    verify(arguments.runtime, arguments.prepared_dir)
    print("verified packaged release trust input custody")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
