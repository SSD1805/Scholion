#!/usr/bin/env python3
"""Build exact release payload/checksum bytes and wrap an offline-produced signature."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from scholion.supply_chain.release_tools import (
    ReleaseArtifactInput,
    assemble_signed_update_envelope,
    build_sha256sums,
    build_update_payload_bytes,
)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def _artifact(value: str) -> ReleaseArtifactInput:
    try:
        platform_id, path_text, url = value.split("::", 2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "artifact must be PLATFORM::LOCAL_PATH::HTTPS_URL"
        ) from exc
    return ReleaseArtifactInput(platform=platform_id, path=Path(path_text), url=url)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Build deterministic Scholion release metadata. Private-key signing remains "
            "external to this tool."
        )
    )
    subcommands = command.add_subparsers(dest="command", required=True)

    payload = subcommands.add_parser("payload", help="Build exact bytes for offline signing")
    payload.add_argument("--sequence", type=int, required=True)
    payload.add_argument("--channel", required=True)
    payload.add_argument("--version", required=True)
    payload.add_argument("--published-at", type=_timestamp, required=True)
    payload.add_argument("--expires-at", type=_timestamp, required=True)
    payload.add_argument("--release-notes-url", required=True)
    payload.add_argument("--artifact", action="append", type=_artifact, required=True)
    payload.add_argument("--output", type=Path, required=True)
    payload.add_argument("--checksums", type=Path, required=True)

    envelope = subcommands.add_parser(
        "envelope", help="Wrap an external raw Ed25519 signature"
    )
    envelope.add_argument("--payload", type=Path, required=True)
    envelope.add_argument("--signature", type=Path, required=True)
    envelope.add_argument("--key-id", required=True)
    envelope.add_argument("--output", type=Path, required=True)
    return command


def main() -> int:
    args = parser().parse_args()
    if args.command == "payload":
        artifacts = tuple(args.artifact)
        payload = build_update_payload_bytes(
            sequence=args.sequence,
            channel=args.channel,
            version=args.version,
            published_at=args.published_at,
            expires_at=args.expires_at,
            release_notes_url=args.release_notes_url,
            artifacts=artifacts,
        )
        args.output.write_bytes(payload)
        args.checksums.write_bytes(build_sha256sums(artifacts))
        print(
            json.dumps(
                {
                    "payload": str(args.output),
                    "checksums": str(args.checksums),
                    "artifacts": len(artifacts),
                    "signing": "external",
                },
                sort_keys=True,
            )
        )
        return 0

    payload = args.payload.read_bytes()
    signature = args.signature.read_bytes()
    args.output.write_bytes(
        assemble_signed_update_envelope(
            payload,
            key_id=args.key_id,
            signature=signature,
        )
    )
    print(json.dumps({"envelope": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
