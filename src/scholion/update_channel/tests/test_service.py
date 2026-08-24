import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from scholion.core.file_manager_facade import FileManagerFacade
from scholion.update_channel import service
from scholion.update_channel.service import (
    UpdateChannelError,
    UpdateChannelService,
    UpdateStateStore,
)

_NOW = datetime(2026, 8, 24, 1, 0, tzinfo=UTC)
_SIGNATURE = b"s" * 64


class _Store:
    def __init__(self) -> None:
        self.files: dict[Path, bytes] = {}
        self.private_directories: set[Path] = set()

    def file_exists(self, path: str | Path) -> bool:
        return Path(path) in self.files

    def read_file(self, path: str | Path) -> bytes:
        return self.files[Path(path)]

    def ensure_directory_exists(
        self, path: str | Path, *, private: bool = False
    ) -> None:
        if private:
            self.private_directories.add(Path(path))

    def save_file(
        self, content: bytes, path: str | Path, *, private: bool = False
    ) -> None:
        assert private
        self.files[Path(path)] = content


class _Verifier:
    def __init__(self, accepted_payload: bytes) -> None:
        self.accepted_payload = accepted_payload
        self.calls = 0

    def verify(
        self,
        *,
        key_id: str,
        algorithm: str,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        self.calls += 1
        return (
            key_id == "release-2026"
            and algorithm == "ed25519"
            and payload == self.accepted_payload
            and signature == _SIGNATURE
        )


class _Transport:
    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest
        self.fetch_calls: list[str] = []
        self.stage_calls: list[dict[str, object]] = []

    def fetch_manifest(self, url: str) -> dict[str, Any]:
        self.fetch_calls.append(url)
        return self.manifest

    def stage_verified_artifact(
        self,
        url: str,
        *,
        destination: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        self.stage_calls.append(
            {
                "url": url,
                "destination": destination,
                "expected_size": expected_size,
                "expected_sha256": expected_sha256,
            }
        )


def _payload(
    *,
    sequence: int = 7,
    version: str = "0.2.0",
    platform_id: str = "windows-x86_64",
    channel: str = "stable",
) -> bytes:
    document = {
        "schema_version": 1,
        "sequence": sequence,
        "channel": channel,
        "version": version,
        "published_at": (_NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (_NOW + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
        "release_notes_url": "https://github.com/SSD1805/Scholion/releases/tag/v0.2.0",
        "artifacts": [
            {
                "platform": platform_id,
                "url": "https://github.com/SSD1805/Scholion/releases/download/v0.2.0/app.bin",
                "size_bytes": 42,
                "sha256": "a" * 64,
            }
        ],
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _envelope(payload: bytes) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "key_id": "release-2026",
        "algorithm": "ed25519",
        "payload_base64": base64.b64encode(payload).decode(),
        "signature_base64": base64.b64encode(_SIGNATURE).decode(),
    }


def _service(
    tmp_path: Path,
    payload: bytes,
    *,
    current_version: str = "0.1.0",
    store: _Store | None = None,
) -> tuple[UpdateChannelService, _Store, _Verifier, _Transport]:
    resolved_store = store or _Store()
    verifier = _Verifier(payload)
    transport = _Transport(_envelope(payload))
    state_store = UpdateStateStore(
        tmp_path / "state", cast(FileManagerFacade, resolved_store)
    )
    channel = UpdateChannelService(
        current_version=current_version,
        cache_dir=tmp_path / "cache",
        state_store=state_store,
        verifier=verifier,
        transport=transport,
        platform_id="windows-x86_64",
    )
    return channel, resolved_store, verifier, transport


def test_source_build_without_verifier_stays_off_and_never_fetches(tmp_path: Path) -> None:
    store = _Store()
    transport = _Transport({})
    channel = UpdateChannelService(
        current_version="0.1.0",
        cache_dir=tmp_path / "cache",
        state_store=UpdateStateStore(
            tmp_path / "state", cast(FileManagerFacade, store)
        ),
        verifier=None,
        transport=transport,
        platform_id="windows-x86_64",
    )

    assert channel.status()["state"] == "off"
    assert channel.check(now=_NOW)["state"] == "off"
    assert channel.stage(now=_NOW)["state"] == "off"
    assert transport.fetch_calls == []


def test_verified_check_persists_monotonic_trust_state(tmp_path: Path) -> None:
    payload = _payload(sequence=7, version="0.2.0")
    channel, store, verifier, transport = _service(tmp_path, payload)

    result = channel.check(now=_NOW)

    assert result["state"] == "trusted_update_available"
    assert result["available_version"] == "0.2.0"
    assert result["download_size_bytes"] == 42
    assert verifier.calls == 1
    assert transport.fetch_calls == [service.FIXED_UPDATE_MANIFEST_URL]
    state = channel.state_store.load()
    assert state.highest_trusted_sequence == 7
    assert state.last_status == "trusted_update_available"
    assert state.trusted_manifest == _envelope(payload)
    assert channel.state_store.state_dir in store.private_directories


def test_same_or_older_release_is_reported_up_to_date(tmp_path: Path) -> None:
    equal, _, _, _ = _service(tmp_path, _payload(version="0.1.0"))
    older, _, _, _ = _service(tmp_path / "older", _payload(version="0.0.9"))

    assert equal.check(now=_NOW)["state"] == "up_to_date"
    assert older.check(now=_NOW)["state"] == "up_to_date"


def test_rollback_is_rejected_against_persisted_sequence(tmp_path: Path) -> None:
    newer_payload = _payload(sequence=8, version="0.3.0")
    first, store, _, _ = _service(tmp_path, newer_payload)
    first.check(now=_NOW)

    older_payload = _payload(sequence=7, version="0.2.0")
    second, _, _, _ = _service(tmp_path, older_payload, store=store)

    with pytest.raises(UpdateChannelError, match="trust verification"):
        second.check(now=_NOW)

    assert second.state_store.load().highest_trusted_sequence == 8


def test_same_sequence_cannot_authorize_different_signed_content(tmp_path: Path) -> None:
    first_payload = _payload(sequence=8, version="0.3.0")
    first, store, _, _ = _service(tmp_path, first_payload)
    first.check(now=_NOW)

    replacement_payload = _payload(sequence=8, version="0.4.0")
    second, _, _, _ = _service(tmp_path, replacement_payload, store=store)

    with pytest.raises(UpdateChannelError, match="different signed content"):
        second.check(now=_NOW)

    persisted = second.state_store.load()
    assert persisted.last_version == "0.3.0"
    assert persisted.trusted_manifest == _envelope(first_payload)


def test_stable_endpoint_rejects_other_signed_channels(tmp_path: Path) -> None:
    payload = _payload(channel="beta")
    channel, _, verifier, _ = _service(tmp_path, payload)

    with pytest.raises(UpdateChannelError, match="not stable"):
        channel.check(now=_NOW)

    assert verifier.calls == 1
    assert channel.state_store.load().highest_trusted_sequence is None


def test_untrusted_signature_does_not_advance_state(tmp_path: Path) -> None:
    payload = _payload()
    channel, _, verifier, transport = _service(tmp_path, payload)
    transport.manifest = _envelope(payload.replace(b"0.2.0", b"9.9.9"))

    with pytest.raises(UpdateChannelError, match="trust verification"):
        channel.check(now=_NOW)

    assert verifier.calls == 1
    assert channel.state_store.load().highest_trusted_sequence is None


def test_platform_must_exist_inside_signed_manifest(tmp_path: Path) -> None:
    payload = _payload(platform_id="macos-aarch64")
    channel, _, _, _ = _service(tmp_path, payload)

    with pytest.raises(UpdateChannelError, match="No trusted update package"):
        channel.check(now=_NOW)


def test_stage_reverifies_cached_manifest_and_uses_only_signed_artifact_data(
    tmp_path: Path,
) -> None:
    payload = _payload(sequence=9, version="1.0.0")
    channel, _, verifier, transport = _service(tmp_path, payload)
    channel.check(now=_NOW)

    staged = channel.stage(now=_NOW)

    assert staged["state"] == "staged"
    assert verifier.calls == 2
    assert transport.stage_calls == [
        {
            "url": "https://github.com/SSD1805/Scholion/releases/download/v0.2.0/app.bin",
            "destination": tmp_path
            / "cache"
            / "updates"
            / "staged"
            / "release-9-windows-x86_64.bin",
            "expected_size": 42,
            "expected_sha256": "a" * 64,
        }
    ]
    assert channel.status()["state"] == "staged"


def test_stage_requires_prior_trusted_check_and_newer_release(tmp_path: Path) -> None:
    payload = _payload(version="0.1.0")
    channel, _, _, _ = _service(tmp_path, payload)

    with pytest.raises(UpdateChannelError, match="Check for a trusted update"):
        channel.stage(now=_NOW)

    channel.check(now=_NOW)
    with pytest.raises(UpdateChannelError, match="not newer"):
        channel.stage(now=_NOW)


def test_state_store_fails_closed_on_malformed_or_partial_state(tmp_path: Path) -> None:
    store = _Store()
    state_store = UpdateStateStore(
        tmp_path / "state", cast(FileManagerFacade, store)
    )
    store.files[state_store.path] = b"not-json"
    with pytest.raises(UpdateChannelError, match="invalid"):
        state_store.load()

    store.files[state_store.path] = json.dumps(
        {
            "schema_version": 1,
            "highest_trusted_sequence": None,
            "last_status": "never_checked",
            "last_version": None,
            "trusted_manifest": {},
        }
    ).encode()
    with pytest.raises(UpdateChannelError, match="has no sequence"):
        state_store.load()


def test_semver_comparison_handles_prerelease_and_build_metadata() -> None:
    assert service._is_newer("1.0.0", "1.0.0-rc.1") is True
    assert service._is_newer("1.0.0-rc.2", "1.0.0-rc.1") is True
    assert service._is_newer("1.0.0-alpha", "1.0.0-alpha.1") is False
    assert service._is_newer("1.0.0+build.2", "1.0.0+build.1") is False
    assert service._is_newer("2.0.0", "1.99.99") is True
    with pytest.raises(UpdateChannelError, match="semantic version"):
        service._is_newer("latest", "1.0.0")


def test_platform_id_is_bounded_to_supported_desktop_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.platform, "machine", lambda: "AMD64")
    assert service.current_platform_id() == "windows-x86_64"

    monkeypatch.setattr(service.platform, "system", lambda: "Plan9")
    with pytest.raises(UpdateChannelError, match="supported update package"):
        service.current_platform_id()
