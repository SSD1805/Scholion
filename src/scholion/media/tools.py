from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from scholion.media.errors import MediaToolUnavailableError

_ALLOWED_MEDIA_TOOLS = frozenset({"ffmpeg", "ffprobe"})
_VERSION_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class MediaToolIdentity:
    """Bounded identity for one resolved media executable."""

    name: str
    source: str
    version: str
    size_bytes: int
    sha256: str


def _tool_filename(name: str) -> str:
    if name not in _ALLOWED_MEDIA_TOOLS:
        raise ValueError(f"unsupported media tool: {name}")
    suffix = ".exe" if sys.platform == "win32" else ""
    return f"{name}{suffix}"


def _frozen_bundle_root() -> Path | None:
    if not bool(getattr(sys, "frozen", False)):
        return None
    raw_root = getattr(sys, "_MEIPASS", None)
    if not isinstance(raw_root, str) or not raw_root:
        raise MediaToolUnavailableError(
            "Packaged Scholion runtime could not resolve its managed media tools"
        )
    try:
        return Path(raw_root).resolve(strict=True)
    except OSError as exc:
        raise MediaToolUnavailableError(
            "Packaged Scholion runtime could not resolve its managed media tools",
            cause=exc,
        ) from exc


def resolve_media_tool(name: str) -> str:
    """Resolve FFmpeg/FFprobe, refusing ambient PATH inside a frozen runtime."""
    filename = _tool_filename(name)
    bundle_root = _frozen_bundle_root()
    if bundle_root is None:
        executable = shutil.which(filename)
        if executable is None:
            raise MediaToolUnavailableError(f"{name} is not installed or not on PATH")
        return executable

    candidate = bundle_root / "media-tools" / filename
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise MediaToolUnavailableError(
            f"Packaged Scholion runtime is missing managed {name}", cause=exc
        ) from exc
    try:
        resolved.relative_to(bundle_root)
    except ValueError as exc:
        raise MediaToolUnavailableError(
            f"Packaged Scholion runtime rejected managed {name} outside its bundle",
            cause=exc,
        ) from exc
    if not resolved.is_file():
        raise MediaToolUnavailableError(
            f"Packaged Scholion runtime managed {name} is not a regular file"
        )
    return str(resolved)


def configure_frozen_media_tool_path() -> None:
    """Constrain legacy PATH lookup to managed media bytes in packaged Scholion."""
    bundle_root = _frozen_bundle_root()
    if bundle_root is None:
        return
    for name in sorted(_ALLOWED_MEDIA_TOOLS):
        resolve_media_tool(name)
    os.environ["PATH"] = str(bundle_root / "media-tools")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_tool_identity(
    name: str, *, timeout_seconds: float = _VERSION_TIMEOUT_SECONDS
) -> MediaToolIdentity:
    """Measure the exact resolved executable without exposing its local path."""
    executable = Path(resolve_media_tool(name))
    try:
        completed = subprocess.run(  # noqa: S603
            [str(executable), "-version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaToolUnavailableError(f"{name} could not be executed", cause=exc) from exc
    if completed.returncode != 0:
        raise MediaToolUnavailableError(f"{name} could not be executed")
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    if not first_line or len(first_line) > 256:
        raise MediaToolUnavailableError(f"{name} returned invalid version identity")
    return MediaToolIdentity(
        name=name,
        source="bundled" if _frozen_bundle_root() is not None else "path",
        version=first_line,
        size_bytes=executable.stat().st_size,
        sha256=_sha256_file(executable),
    )
