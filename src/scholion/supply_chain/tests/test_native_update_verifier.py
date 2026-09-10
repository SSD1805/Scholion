from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scholion.supply_chain.native_update_verifier import (
    NativeUpdateVerifier,
    discover_packaged_native_verifier,
)


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
        "payload": list(b"exact signed bytes"),
        "protocol_version": 1,
        "signature": list(b"s" * 64),
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


def _freeze(
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime: Path,
    platform: str,
    candidate: Path | None,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(runtime))
    monkeypatch.setattr(sys, "platform", platform)
    if candidate is None:
        monkeypatch.delenv("SCHOLION_NATIVE_UPDATE_VERIFIER", raising=False)
    else:
        monkeypatch.setenv("SCHOLION_NATIVE_UPDATE_VERIFIER", str(candidate))


def test_source_runtime_never_discovers_environment_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "native"
    candidate.write_bytes(b"native")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("SCHOLION_NATIVE_UPDATE_VERIFIER", str(candidate))

    assert discover_packaged_native_verifier() is None


def test_windows_frozen_runtime_accepts_only_same_install_root_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "install"
    runtime = install / "runtime" / "scholion-runtime.exe"
    candidate = install / "scholion-desktop.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime")
    candidate.write_bytes(b"native")
    _freeze(
        monkeypatch,
        runtime=runtime,
        platform="win32",
        candidate=candidate,
    )

    verifier = discover_packaged_native_verifier()

    assert verifier == NativeUpdateVerifier(candidate.resolve())


def test_macos_frozen_runtime_accepts_only_contents_macos_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contents = tmp_path / "Scholion.app" / "Contents"
    runtime = contents / "Resources" / "runtime" / "scholion-runtime"
    candidate = contents / "MacOS" / "scholion-desktop"
    runtime.parent.mkdir(parents=True)
    candidate.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime")
    candidate.write_bytes(b"native")
    _freeze(
        monkeypatch,
        runtime=runtime,
        platform="darwin",
        candidate=candidate,
    )

    verifier = discover_packaged_native_verifier()

    assert verifier == NativeUpdateVerifier(candidate.resolve())


def test_frozen_runtime_rejects_external_native_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "install"
    runtime = install / "runtime" / "scholion-runtime.exe"
    external = tmp_path / "attacker" / "verifier.exe"
    runtime.parent.mkdir(parents=True)
    external.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime")
    external.write_bytes(b"external")
    _freeze(
        monkeypatch,
        runtime=runtime,
        platform="win32",
        candidate=external,
    )

    assert discover_packaged_native_verifier() is None


def test_frozen_runtime_without_native_host_stays_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime" / "scholion-runtime"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime")
    _freeze(
        monkeypatch,
        runtime=runtime,
        platform=sys.platform,
        candidate=None,
    )

    assert discover_packaged_native_verifier() is None
