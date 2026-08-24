from __future__ import annotations

import json
import os
import platform
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scholion.core.file_manager_facade import FileManagerFacade
from scholion.supply_chain.update_manifest import (
    SignatureVerifier,
    UpdateTrustError,
    verify_signed_update_manifest,
)

FIXED_UPDATE_MANIFEST_URL = (
    "https://github.com/SSD1805/Scholion/releases/latest/download/scholion-update.json"
)
_STATE_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 64 * 1024
_HTTP_TIMEOUT_SECONDS = 12.0
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


class UpdateChannelError(ValueError):
    """Raised when the application update channel must fail closed."""


class UpdateTransport(Protocol):
    def fetch_manifest(self, url: str) -> dict[str, Any]: ...

    def stage_verified_artifact(
        self,
        url: str,
        *,
        destination: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None: ...


def _require_https(value: str, field: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise UpdateChannelError(f"{field} must be a credential-free HTTPS URL")


def _read_bounded(response: Any, limit: int) -> bytes:
    content = response.read(limit + 1)
    if len(content) > limit:
        raise UpdateChannelError("Update metadata exceeded the safe size limit")
    return content


def _copy_bounded_artifact(
    response: Any,
    temporary: Any,
    *,
    expected_size: int,
) -> tuple[int, str]:
    digest = sha256()
    total = 0
    while True:
        chunk = response.read(_DOWNLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > expected_size:
            raise UpdateChannelError("Downloaded update exceeded its signed size")
        digest.update(chunk)
        temporary.write(chunk)
    return total, digest.hexdigest()


class HttpsUpdateTransport:
    """Small HTTPS-only transport with no installation or behavioral identifier."""

    def __init__(self, timeout_seconds: float = _HTTP_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0:
            raise ValueError("update timeout must be positive")
        self.timeout_seconds = timeout_seconds

    def fetch_manifest(self, url: str) -> dict[str, Any]:
        _require_https(url, "update manifest URL")
        request = Request(  # noqa: S310 - URL is HTTPS-only and validated above.
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Scholion-update-check",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                _require_https(response.geturl(), "resolved update manifest URL")
                raw = _read_bounded(response, _MAX_MANIFEST_BYTES)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise UpdateChannelError("Update metadata could not be fetched") from exc
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateChannelError("Update metadata was not valid JSON") from exc
        if not isinstance(document, dict):
            raise UpdateChannelError("Update metadata must be a JSON object")
        return document

    def stage_verified_artifact(
        self,
        url: str,
        *,
        destination: Path,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        _require_https(url, "update artifact URL")
        if expected_size < 1:
            raise UpdateChannelError("Trusted update artifact size must be positive")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise UpdateChannelError("Trusted update artifact hash is invalid")

        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        request = Request(  # noqa: S310 - URL is HTTPS-only and validated above.
            url,
            headers={
                "Accept": "application/octet-stream",
                "User-Agent": "Scholion-update-download",
            },
            method="GET",
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                delete=False,
                dir=destination.parent,
            ) as temporary:
                temporary_path = Path(temporary.name)
                if os.name != "nt":
                    os.chmod(temporary_path, 0o600)
                with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                    _require_https(response.geturl(), "resolved update artifact URL")
                    total, observed_sha256 = _copy_bounded_artifact(
                        response,
                        temporary,
                        expected_size=expected_size,
                    )
                temporary.flush()
                os.fsync(temporary.fileno())

            self._commit_verified_artifact(
                temporary_path,
                destination,
                total=total,
                observed_sha256=observed_sha256,
                expected_size=expected_size,
                expected_sha256=expected_sha256,
            )
            temporary_path = None
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise UpdateChannelError(
                "Trusted update artifact could not be staged"
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _commit_verified_artifact(
        temporary_path: Path,
        destination: Path,
        *,
        total: int,
        observed_sha256: str,
        expected_size: int,
        expected_sha256: str,
    ) -> None:
        if total != expected_size:
            raise UpdateChannelError(
                "Downloaded update size did not match signed metadata"
            )
        if observed_sha256 != expected_sha256:
            raise UpdateChannelError(
                "Downloaded update hash did not match signed metadata"
            )
        os.replace(temporary_path, destination)
        if os.name != "nt":
            os.chmod(destination, 0o600)


@dataclass(frozen=True, slots=True)
class UpdateTrustState:
    highest_trusted_sequence: int | None = None
    last_status: str = "never_checked"
    last_version: str | None = None
    trusted_manifest: dict[str, Any] | None = None


class UpdateStateStore:
    """Persist local anti-rollback state without generating an installation identity."""

    def __init__(self, state_dir: Path, file_store: FileManagerFacade) -> None:
        self.state_dir = state_dir.expanduser().resolve(strict=False) / "updates"
        self.path = self.state_dir / "trust-state.json"
        self.file_store = file_store

    def load(self) -> UpdateTrustState:
        if not self.file_store.file_exists(self.path):
            return UpdateTrustState()
        try:
            document = json.loads(self.file_store.read_file(self.path).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateChannelError("Stored update trust state is invalid") from exc
        if not isinstance(document, dict):
            raise UpdateChannelError("Stored update trust state must be an object")
        expected = {
            "schema_version",
            "highest_trusted_sequence",
            "last_status",
            "last_version",
            "trusted_manifest",
        }
        if (
            set(document) != expected
            or document.get("schema_version") != _STATE_SCHEMA_VERSION
        ):
            raise UpdateChannelError(
                "Stored update trust state has an unsupported schema"
            )

        sequence = document.get("highest_trusted_sequence")
        if sequence is not None and (
            not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1
        ):
            raise UpdateChannelError("Stored update sequence is invalid")
        status = document.get("last_status")
        if status not in {
            "never_checked",
            "up_to_date",
            "trusted_update_available",
            "staged",
        }:
            raise UpdateChannelError("Stored update status is invalid")
        version = document.get("last_version")
        if version is not None and (
            not isinstance(version, str) or not version.strip()
        ):
            raise UpdateChannelError("Stored update version is invalid")
        manifest = document.get("trusted_manifest")
        if manifest is not None and not isinstance(manifest, dict):
            raise UpdateChannelError("Stored trusted update manifest is invalid")
        if manifest is not None and sequence is None:
            raise UpdateChannelError("Stored trusted update manifest has no sequence")
        return UpdateTrustState(
            highest_trusted_sequence=sequence,
            last_status=status,
            last_version=version,
            trusted_manifest=manifest,
        )

    def save(self, state: UpdateTrustState) -> None:
        self.file_store.ensure_directory_exists(self.state_dir, private=True)
        document = {
            "schema_version": _STATE_SCHEMA_VERSION,
            "highest_trusted_sequence": state.highest_trusted_sequence,
            "last_status": state.last_status,
            "last_version": state.last_version,
            "trusted_manifest": state.trusted_manifest,
        }
        self.file_store.save_file(
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            self.path,
            private=True,
        )


def current_platform_id() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }.get(machine)
    operating_system = {
        "windows": "windows",
        "darwin": "macos",
        "linux": "linux",
    }.get(system)
    if architecture is None or operating_system is None:
        raise UpdateChannelError(
            "This platform does not have a supported update package"
        )
    return f"{operating_system}-{architecture}"


def _semver_parts(value: str) -> tuple[tuple[int, int, int], tuple[str, ...] | None]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise UpdateChannelError("Release version is not valid semantic version text")
    core = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    prerelease = match.group(4)
    return core, None if prerelease is None else tuple(prerelease.split("."))


def _compare_prerelease(
    first: tuple[str, ...] | None,
    second: tuple[str, ...] | None,
) -> int:
    if first is None and second is None:
        return 0
    if first is None:
        return 1
    if second is None:
        return -1
    for left, right in zip(first, second, strict=False):
        if left == right:
            continue
        left_numeric = left.isdigit()
        right_numeric = right.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left) < int(right) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left < right else 1
    if len(first) == len(second):
        return 0
    return -1 if len(first) < len(second) else 1


def _is_newer(remote: str, current: str) -> bool:
    remote_core, remote_pre = _semver_parts(remote)
    current_core, current_pre = _semver_parts(current)
    if remote_core != current_core:
        return remote_core > current_core
    return _compare_prerelease(remote_pre, current_pre) > 0


class UpdateChannelService:
    """Authorize update metadata, persist rollback state, and stage exact trusted bytes."""

    def __init__(
        self,
        *,
        current_version: str,
        cache_dir: Path,
        state_store: UpdateStateStore,
        verifier: SignatureVerifier | None,
        transport: UpdateTransport | None = None,
        manifest_url: str = FIXED_UPDATE_MANIFEST_URL,
        platform_id: str | None = None,
        expected_channel: str = "stable",
    ) -> None:
        _semver_parts(current_version)
        _require_https(manifest_url, "update manifest URL")
        if not expected_channel.strip():
            raise ValueError("expected update channel cannot be empty")
        self.current_version = current_version
        self.cache_dir = cache_dir.expanduser().resolve(strict=False)
        self.state_store = state_store
        self.verifier = verifier
        self.transport = transport or HttpsUpdateTransport()
        self.manifest_url = manifest_url
        self.platform_id = platform_id or current_platform_id()
        self.expected_channel = expected_channel

    def status(self) -> dict[str, object]:
        if self.verifier is None:
            return {
                "enabled": False,
                "state": "off",
                "current_version": self.current_version,
                "message": (
                    "This build does not contain a production update trust key. "
                    "Local and offline work is unaffected."
                ),
            }
        state = self.state_store.load()
        return {
            "enabled": True,
            "state": state.last_status,
            "current_version": self.current_version,
            "available_version": state.last_version,
            "message": self._message(state.last_status, state.last_version),
        }

    def check(self, *, now: datetime | None = None) -> dict[str, object]:
        if self.verifier is None:
            return self.status()
        state = self.state_store.load()
        document = self.transport.fetch_manifest(self.manifest_url)
        try:
            payload = verify_signed_update_manifest(
                document,
                verifier=self.verifier,
                now=now or datetime.now(UTC),
                highest_seen_sequence=state.highest_trusted_sequence,
            )
        except UpdateTrustError as exc:
            raise UpdateChannelError(
                "Update metadata did not pass trust verification"
            ) from exc

        self._require_expected_channel(payload.channel)
        if (
            state.highest_trusted_sequence == payload.sequence
            and state.trusted_manifest is not None
            and state.trusted_manifest != document
        ):
            raise UpdateChannelError(
                "Update metadata reused a trusted sequence with different signed content"
            )

        try:
            artifact = payload.artifact_for(self.platform_id)
        except UpdateTrustError as exc:
            raise UpdateChannelError(
                "No trusted update package is available for this platform"
            ) from exc

        next_status = (
            "trusted_update_available"
            if _is_newer(payload.version, self.current_version)
            else "up_to_date"
        )
        trusted_state = UpdateTrustState(
            highest_trusted_sequence=payload.sequence,
            last_status=next_status,
            last_version=payload.version,
            trusted_manifest=document,
        )
        self.state_store.save(trusted_state)
        return {
            "enabled": True,
            "state": next_status,
            "current_version": self.current_version,
            "available_version": payload.version,
            "release_notes_url": payload.release_notes_url,
            "download_size_bytes": artifact.size_bytes,
            "message": self._message(next_status, payload.version),
        }

    def stage(self, *, now: datetime | None = None) -> dict[str, object]:
        if self.verifier is None:
            return self.status()
        state = self.state_store.load()
        if state.trusted_manifest is None or state.highest_trusted_sequence is None:
            raise UpdateChannelError("Check for a trusted update before downloading it")
        try:
            payload = verify_signed_update_manifest(
                state.trusted_manifest,
                verifier=self.verifier,
                now=now or datetime.now(UTC),
                highest_seen_sequence=state.highest_trusted_sequence,
            )
            artifact = payload.artifact_for(self.platform_id)
        except UpdateTrustError as exc:
            raise UpdateChannelError(
                "Stored update metadata is no longer trusted"
            ) from exc
        self._require_expected_channel(payload.channel)
        if not _is_newer(payload.version, self.current_version):
            raise UpdateChannelError("The trusted release is not newer than this build")

        staging_dir = self.cache_dir / "updates" / "staged"
        destination = staging_dir / f"release-{payload.sequence}-{self.platform_id}.bin"
        self.transport.stage_verified_artifact(
            artifact.url,
            destination=destination,
            expected_size=artifact.size_bytes,
            expected_sha256=artifact.sha256_hex,
        )
        staged_state = UpdateTrustState(
            highest_trusted_sequence=payload.sequence,
            last_status="staged",
            last_version=payload.version,
            trusted_manifest=state.trusted_manifest,
        )
        self.state_store.save(staged_state)
        return {
            "enabled": True,
            "state": "staged",
            "current_version": self.current_version,
            "available_version": payload.version,
            "download_size_bytes": artifact.size_bytes,
            "message": self._message("staged", payload.version),
        }

    def _require_expected_channel(self, channel: str) -> None:
        if channel != self.expected_channel:
            raise UpdateChannelError(
                f"Signed update channel is not {self.expected_channel}"
            )

    @staticmethod
    def _message(status: str, version: str | None) -> str:
        if status == "never_checked":
            return "Scholion has not checked for updates on this computer."
        if status == "up_to_date":
            return "This Scholion version is up to date."
        if status == "trusted_update_available":
            return f"A trusted Scholion update is available: {version}."
        if status == "staged":
            return f"Scholion verified and staged update {version} for installation."
        raise UpdateChannelError("Stored update status is unsupported")
