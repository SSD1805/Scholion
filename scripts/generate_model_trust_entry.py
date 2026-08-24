#!/usr/bin/env python3
"""Measure one reviewed immutable model snapshot into JSON policy material."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scholion.supply_chain.catalog_generation import generate_trusted_model_spec


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Measure a deliberately reviewed immutable model snapshot. This does not make "
            "the snapshot trusted until the resulting JSON is reviewed and bundled."
        )
    )
    command.add_argument("--model-id", required=True)
    command.add_argument("--engine", required=True)
    command.add_argument("--repository-id", required=True)
    command.add_argument("--revision", required=True)
    command.add_argument("--source-url", required=True)
    command.add_argument("--license-id", required=True)
    command.add_argument("--license-url", required=True)
    command.add_argument("--snapshot-root", required=True, type=Path)
    command.add_argument("--cache-root", required=True, type=Path)
    command.add_argument("--output", type=Path)
    return command


def main() -> int:
    args = parser().parse_args()
    spec = generate_trusted_model_spec(
        model_id=args.model_id,
        engine=args.engine,
        repository_id=args.repository_id,
        revision=args.revision,
        source_url=args.source_url,
        license_id=args.license_id,
        license_url=args.license_url,
        snapshot_root=args.snapshot_root,
        cache_root=args.cache_root,
    )
    rendered = json.dumps(spec.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
