from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

_NATIVE_PROTOCOL_VERSION = 1
_NATIVE_VERIFY_ARGUMENT = "--scholion-verify-update-signature"
_MAX_RESPONSE_BYTES = 4096
_VERIFY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class NativeUpdateVerifier:
    """Adapt Scholion's signature-verifier contract to the native Rust host.

    The executable path is supplied by trusted application composition. This class does
    not discover an executable from PATH or caller-controlled request data.
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
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "signature_base64": base64.b64encode(signature).decode("ascii"),
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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
