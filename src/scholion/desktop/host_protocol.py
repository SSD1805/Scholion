"""Shared mechanics for fixed trusted-host Python bridges.

This module owns only the versioned stdin/stdout transport envelope. It deliberately knows
nothing about desktop methods, application services, filesystem paths, or Tauri commands.
Each bridge keeps its own closed request schema, dispatcher, service composition, and public
error policy.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from contextlib import redirect_stdout

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 128 * 1024

BridgeResponse = dict[str, object]
BridgeHandler = Callable[[object], BridgeResponse]


def success_response(request_id: str, result: object) -> BridgeResponse:
    """Build the common successful trusted-host response envelope."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": result,
        "error": None,
    }


def failure_response(request_id: str, *, code: str, message: str) -> BridgeResponse:
    """Build the common failed trusted-host response envelope."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": False,
        "result": None,
        "error": {"code": code, "message": message},
    }


def _request_id(payload: object) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    value = payload.get("request_id")
    if not isinstance(value, str) or not value:
        return "unknown"
    return value[:128]


def run_stdio_bridge(
    handler: BridgeHandler,
    *,
    oversized_message: str,
    invalid_json_message: str,
) -> int:
    """Run one bounded JSON request without broadening a bridge's authority.

    ``handler`` remains bridge-specific. Constructing services inside it happens while
    stdout is redirected to stderr so application diagnostics cannot corrupt the single
    JSON response expected by the Rust host. Unexpected handler/bootstrap failures are
    normalized into one bounded protocol response instead of crashing the Python process.
    """
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        response = failure_response(
            "unknown",
            code="invalid_request",
            message=oversized_message,
        )
    else:
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = failure_response(
                "unknown",
                code="invalid_request",
                message=invalid_json_message,
            )
        else:
            try:
                with redirect_stdout(sys.stderr):
                    response = handler(payload)
            except Exception:
                response = failure_response(
                    _request_id(payload),
                    code="internal_error",
                    message="Scholion could not initialize the local desktop service",
                )

    sys.stdout.write(json.dumps(response, sort_keys=True))
    sys.stdout.write("\n")
    return 0
