#!/usr/bin/env python3
"""Build Scholion's public-only production update verification catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scholion.supply_chain.release_trust_inputs import ReleaseTrustInputError
from scholion.supply_chain.update_key_catalog import build_update_key_catalog


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Build deterministic public update-key catalog bytes from Ed25519 "
            "SubjectPublicKeyInfo DER files. Private keys are not accepted."
        )
    )
    command.add_argument("--current-key-id", required=True)
    command.add_argument("--current-public-key-der", type=Path, required=True)
    command.add_argument("--next-key-id")
    command.add_argument("--next-public-key-der", type=Path)
    command.add_argument("--output", type=Path, required=True)
    return command


def main() -> int:
    args = parser().parse_args()
    try:
        payload = build_update_key_catalog(
            current_key_id=args.current_key_id,
            current_public_key_der=args.current_public_key_der,
            next_key_id=args.next_key_id,
            next_public_key_der=args.next_public_key_der,
        )
    except ReleaseTrustInputError as exc:
        raise SystemExit(f"refusing to build update-key catalog: {exc}") from exc

    args.output.write_bytes(payload)
    document = json.loads(payload.decode("utf-8"))
    print(
        json.dumps(
            {
                "output": str(args.output),
                "keys": [
                    {"key_id": item["key_id"], "state": item["state"]}
                    for item in document["keys"]
                ],
                "private_key_material": "not accepted",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
