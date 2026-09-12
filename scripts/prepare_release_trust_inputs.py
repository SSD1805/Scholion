#!/usr/bin/env python3
"""Validate and stage externally approved release trust inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from scholion.supply_chain.release_trust_inputs import prepare_release_trust_inputs


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Validate and stage approved public update keys plus a reviewed model trust "
            "catalog. This command never creates trust material."
        )
    )
    command.add_argument("--update-key-catalog", required=True, type=Path)
    command.add_argument("--model-trust-catalog", required=True, type=Path)
    command.add_argument("--output", required=True, type=Path)
    return command


def main() -> int:
    args = parser().parse_args()
    prepared = prepare_release_trust_inputs(
        update_key_catalog=args.update_key_catalog,
        model_trust_catalog=args.model_trust_catalog,
        output_dir=args.output,
    )
    print(prepared.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
