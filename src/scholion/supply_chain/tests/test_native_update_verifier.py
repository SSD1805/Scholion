from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scholion.supply_chain.native_update_verifier import NativeUpdateVerifier


def _completed(*, stdout: bytes, returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=b"", returncode=returncode)


def test_native_update_verifier_sends_exact_bounded_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        seen["args"] = args
        seen.update(kwargs)
        return _completed(stdout=b'{"protocol_version":1,"verified":true}')

    monkeypatch.setattr(subprocess, "run", fake_run)
    verifier = NativeUpdateVerifier(Path("/trusted/scholion-native"))

    assert verifier.verify(
        key_id="release-2026-a",
        algorithm="ed25519",
        payload=b"exact signed bytes",
        signature=b"s" * 64,
    )

    assert seen["args"] == [
        "/trusted/scholion-native",
        "--scholion-verify-update-signature",
    ]
    assert seen["check"] is False
    assert seen["timeout"] == 5.0
    request = json.loads(seen["input"])
    assert request == {
        "algorithm": "ed25519",
        "key_id": "release-2026-a",
        "payload_base64": base64.b64encode(b"exact signed bytes").decode("ascii"),
        "protocol_version": 1,
        "signature_base64": base64.b64encode(b"s" * 64).decode("ascii"),
    }


@pytest.mark.parametrize(
    ("stdout", "returncode"),
    [
        (b'{"protocol_version":1,"verified":false}', 0),
        (b'{"protocol_version":2,"verified":true}', 0),
        (b'{"protocol_version":1,"verified":true,"extra":1}', 0),
        (b"not-json", 0),
        (b'{"protocol_version":1,"verified":true}', 2),
        (b"x" * 4097, 0),
    ],
)
def test_native_update_verifier_fails_closed_on_invalid_response(
    stdout: bytes,
    returncode: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout=stdout, returncode=returncode),
    )

    assert not NativeUpdateVerifier(Path("/trusted/native")).verify(
        key_id="release-2026-a",
        algorithm="ed25519",
        payload=b"payload",
        signature=b"s" * 64,
    )


def test_native_update_verifier_fails_closed_on_process_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError("missing")

    monkeypatch.setattr(subprocess, "run", fail)

    assert not NativeUpdateVerifier(Path("/trusted/native")).verify(
        key_id="release-2026-a",
        algorithm="ed25519",
        payload=b"payload",
        signature=b"s" * 64,
    )


def test_native_update_verifier_fails_closed_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["native"], timeout=5.0)

    monkeypatch.setattr(subprocess, "run", timeout)

    assert not NativeUpdateVerifier(Path("/trusted/native")).verify(
        key_id="release-2026-a",
        algorithm="ed25519",
        payload=b"payload",
        signature=b"s" * 64,
    )
