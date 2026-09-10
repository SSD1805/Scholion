from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_NATIVE_PROTOCOL_VERSION = 1
_NATIVE_VERIFY_ARGUMENT = "--scholion-verify-update-signature"
_NATIVE_VERIFIER_ENV = "SCHOLION_NATIVE_UPDATE_VERIFIER"
_MAX_RESPONSE_BYTES = 4096
_VERIFY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class NativeUpdateVerifier:
    """Adapt Scholion's signature-verifier contract to the native Rust host.

    The executable path is supplied by trusted packaged application composition. This
    class never resolves a verifier from PATH or caller-controlled request data.
    """

    executable: Path

    def verify(
        self,
        *,
        key_id: str,
        algorithm: str,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        request = {
            "protocol_version": _NATIVE_PROTOCOL_VERSION,
            "key_id": key_id,
            "algorithm": algorithm,
            "payload": list(payload),
            "signature": list(signature),
        }
        encoded = json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            completed = subprocess.run(  # noqa: S603
                [str(self.executable), _NATIVE_VERIFY_ARGUMENT],
                input=encoded,
                capture_output=True,
                check=False,
                timeout=_VERIFY_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

        if completed.returncode != 0 or len(completed.stdout) > _MAX_RESPONSE_BYTES:
            return False
        try:
            response = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(response, dict) or set(response) != {
            "protocol_version",
            "verified",
        }:
            return False
        return (
            response.get("protocol_version") == _NATIVE_PROTOCOL_VERSION
            and isinstance(response.get("verified"), bool)
            and response["verified"]
        )


def _is_expected_packaged_host(runtime: Path, candidate: Path) -> bool:
    if sys.platform == "win32":
        # <install>/runtime/scholion-runtime.exe -> <install>/<native-host>.exe
        return candidate.parent == runtime.parent.parent
    if sys.platform == "darwin":
        # <app>/Contents/Resources/runtime/scholion-runtime
        # <app>/Contents/MacOS/<native-host>
        contents = runtime.parent.parent.parent
        return (
            contents.name == "Contents"
            and candidate.parent.name == "MacOS"
            and candidate.parent.parent == contents
        )
    return False


def discover_packaged_native_verifier() -> NativeUpdateVerifier | None:
    """Return the Rust verifier only when the frozen package supplied its own host.

    Release Tauri composition sets the environment value to its own current executable.
    We still verify the candidate is a real file in the exact package-relative native-host
    location. Source builds, unsupported platforms, missing files, and arbitrary external
    paths remain fail-closed with update checking disabled.
    """

    if not getattr(sys, "frozen", False):
        return None
    raw_candidate = os.environ.get(_NATIVE_VERIFIER_ENV, "").strip()
    if not raw_candidate:
        return None
    try:
        runtime = Path(sys.executable).resolve(strict=True)
        candidate = Path(raw_candidate).expanduser().resolve(strict=True)
    except OSError:
        return None
    if not candidate.is_file() or candidate == runtime:
        return None
    if not _is_expected_packaged_host(runtime, candidate):
        return None
    return NativeUpdateVerifier(candidate)
