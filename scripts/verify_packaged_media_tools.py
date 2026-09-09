from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_tool_identity(document: object, name: str) -> None:
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


def verify(runtime: Path) -> None:
    runtime = runtime.resolve(strict=True)
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
        raise RuntimeError("Packaged runtime did not report the exact managed media-tool set")
    _require_tool_identity(media_tools["ffmpeg"], "ffmpeg")
    _require_tool_identity(media_tools["ffprobe"], "ffprobe")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prove a frozen Scholion runtime owns FFmpeg/FFprobe without PATH."
    )
    parser.add_argument("--runtime", type=Path, required=True)
    arguments = parser.parse_args()
    verify(arguments.runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
