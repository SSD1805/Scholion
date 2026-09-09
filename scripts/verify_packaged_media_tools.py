from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_tool_identity(document: object, name: str) -> dict[str, object]:
    if not isinstance(document, dict):
        raise RuntimeError(f"Packaged runtime did not report {name} identity")
    if document.get("source") != "bundled":
        raise RuntimeError(f"Packaged runtime {name} did not resolve from its bundle")
    version = document.get("version")
    if not isinstance(version, str) or "9.0" not in version or len(version) > 256:
        raise RuntimeError(f"Packaged runtime {name} is outside FFmpeg 9.0 family")
    size = document.get("size_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise RuntimeError(f"Packaged runtime {name} size identity is invalid")
    digest = document.get("sha256")
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise RuntimeError(f"Packaged runtime {name} digest identity is invalid")
    return document


def _expected_tools(evidence_path: Path) -> dict[str, dict[str, object]]:
    try:
        document: Any = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Managed media-tool preparation evidence is invalid"
        ) from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise RuntimeError(
            "Managed media-tool preparation evidence has unsupported schema"
        )
    raw_tools = document.get("tools")
    if not isinstance(raw_tools, list) or len(raw_tools) != 2:
        raise RuntimeError("Managed media-tool preparation evidence has wrong tool set")
    expected: dict[str, dict[str, object]] = {}
    for raw in raw_tools:
        if not isinstance(raw, dict):
            raise RuntimeError(
                "Managed media-tool preparation evidence has invalid tool"
            )
        raw_name = raw.get("name")
        if not isinstance(raw_name, str):
            raise RuntimeError(
                "Managed media-tool preparation evidence has invalid tool name"
            )
        name = raw_name.removesuffix(".exe")
        if name not in {"ffmpeg", "ffprobe"} or name in expected:
            raise RuntimeError(
                "Managed media-tool preparation evidence has wrong tool set"
            )
        expected[name] = raw
    if set(expected) != {"ffmpeg", "ffprobe"}:
        raise RuntimeError("Managed media-tool preparation evidence has wrong tool set")
    return expected


def _assert_matches_prepared(
    actual: dict[str, object], expected: dict[str, object], name: str
) -> None:
    for field in ("size_bytes", "sha256", "version"):
        if actual.get(field) != expected.get(field):
            raise RuntimeError(
                f"Packaged runtime {name} does not match prepared {field} evidence"
            )


def verify(runtime: Path, evidence_path: Path) -> None:
    runtime = runtime.resolve(strict=True)
    expected = _expected_tools(evidence_path.resolve(strict=True))
    env = os.environ.copy()
    env["PATH"] = ""
    try:
        completed = subprocess.run(  # noqa: S603
            [str(runtime), "runtime-info"],
            capture_output=True,
            check=True,
            env=env,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "Packaged runtime could not report managed media-tool identity without PATH"
        ) from exc
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Packaged runtime identity is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Packaged runtime identity must be a JSON object")
    media_tools = payload.get("media_tools")
    if not isinstance(media_tools, dict) or set(media_tools) != {"ffmpeg", "ffprobe"}:
        raise RuntimeError(
            "Packaged runtime did not report the exact managed media-tool set"
        )
    for name in ("ffmpeg", "ffprobe"):
        actual = _require_tool_identity(media_tools[name], name)
        _assert_matches_prepared(actual, expected[name], name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove frozen Scholion owns the exact prepared FFmpeg/FFprobe bytes."
    )
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    arguments = parser.parse_args()
    verify(arguments.runtime, arguments.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
