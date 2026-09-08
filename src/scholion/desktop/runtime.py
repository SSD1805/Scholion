"""Closed entrypoint used by the packaged Scholion desktop runtime.

The native host may select only the finite bridge/worker modes declared here. This is
intentionally not a generic Python module launcher or shell escape hatch.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from importlib import import_module, metadata

from scholion.desktop import (
    bridge,
    custody_bridge,
    playback_bridge,
    processing_worker,
    transcript_tools_bridge,
    update_bridge,
)

_RUNTIME_PROTOCOL_VERSION = 1
_RUNTIME_CAPABILITY_MODULES = (
    "ctranslate2",
    "duckdb",
    "faster_whisper",
    "lingua",
)


def _runtime_info() -> int:
    """Emit bounded non-sensitive runtime identity for package qualification."""
    # The build script explicitly collects these optional distributions. Import them
    # here so qualification proves the frozen runtime can load the capability graph,
    # without making Scholion's ordinary static-analysis environment install it.
    for module_name in _RUNTIME_CAPABILITY_MODULES:
        import_module(module_name)

    payload = {
        "protocol_version": _RUNTIME_PROTOCOL_VERSION,
        "runtime": "scholion-desktop",
        "scholion_version": metadata.version("scholion"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "faster_whisper_version": metadata.version("faster-whisper"),
        "ctranslate2_version": metadata.version("ctranslate2"),
        "duckdb_version": metadata.version("duckdb"),
        "lingua_version": metadata.version("lingua-language-detector"),
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True))
    sys.stdout.write("\n")
    return 0


_HANDLERS: dict[str, Callable[[], int]] = {
    "bridge": bridge.main,
    "custody": custody_bridge.main,
    "playback": playback_bridge.main,
    "processing-worker": processing_worker.main,
    "runtime-info": _runtime_info,
    "transcript-tools": transcript_tools_bridge.main,
    "update": update_bridge.main,
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        sys.stderr.write("Scholion packaged runtime requires exactly one closed mode\n")
        return 2
    handler = _HANDLERS.get(arguments[0])
    if handler is None:
        sys.stderr.write("Scholion packaged runtime mode is unsupported\n")
        return 2
    return handler()


if __name__ == "__main__":
    raise SystemExit(main())
