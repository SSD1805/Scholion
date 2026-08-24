import base64
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from scholion.supply_chain.release_tools import (
    ReleaseArtifactInput,
    assemble_signed_update_envelope,
    build_sha256sums,
    build_update_payload_bytes,
)
from scholion.supply_chain.update_manifest import (
    SignedUpdateEnvelope,
    UpdateManifestPayload,
    UpdateTrustError,
)

_NOW = datetime(2026, 8, 24, 1, 0, tzinfo=UTC)


def _artifact(
    tmp_path: Path, platform: str, name: str, content: bytes
) -> ReleaseArtifactInput:
    path = tmp_path / name
    path.write_bytes(content)
    return ReleaseArtifactInput(
        platform=platform,
        path=path,
        url=f"https://github.com/SSD1805/Scholion/releases/download/v1.0.0/{name}",
    )


def test_payload_is_deterministic_sorted_and_runtime_parseable(tmp_path: Path) -> None:
    windows = _artifact(tmp_path, "windows-x86_64", "scholion.exe", b"windows")
    macos = _artifact(tmp_path, "macos-aarch64", "scholion.app.tar.gz", b"mac")

    first = build_update_payload_bytes(
        sequence=12,
        channel="stable",
        version="1.0.0",
        published_at=_NOW,
        expires_at=_NOW + timedelta(days=7),
        release_notes_url="https://github.com/SSD1805/Scholion/releases/tag/v1.0.0",
        artifacts=(windows, macos),
    )
    second = build_update_payload_bytes(
        sequence=12,
        channel="stable",
        version="1.0.0",
        published_at=_NOW,
        expires_at=_NOW + timedelta(days=7),
        release_notes_url="https://github.com/SSD1805/Scholion/releases/tag/v1.0.0",
        artifacts=(macos, windows),
    )

    assert first == second
    parsed = UpdateManifestPayload.from_bytes(first)
    assert tuple(item.platform for item in parsed.artifacts) == (
        "macos-aarch64",
        "windows-x86_64",
    )
    assert parsed.artifact_for("windows-x86_64").size_bytes == 7


def test_payload_rejects_duplicate_platforms_through_runtime_schema(
    tmp_path: Path,
) -> None:
    first = _artifact(tmp_path, "windows-x86_64", "a.bin", b"a")
    second = _artifact(tmp_path, "windows-x86_64", "b.bin", b"b")

    with pytest.raises(UpdateTrustError, match="platforms must be unique"):
        build_update_payload_bytes(
            sequence=1,
            channel="stable",
            version="1.0.0",
            published_at=_NOW,
            expires_at=_NOW + timedelta(days=1),
            release_notes_url="https://example.test/release",
            artifacts=(first, second),
        )


def test_payload_builder_refuses_non_stable_channel_before_signing(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, "windows-x86_64", "app.bin", b"artifact")

    with pytest.raises(ValueError, match="only emits the stable channel"):
        build_update_payload_bytes(
            sequence=1,
            channel="beta",
            version="1.0.0",
            published_at=_NOW,
            expires_at=_NOW + timedelta(days=1),
            release_notes_url="https://example.test/release",
            artifacts=(artifact,),
        )


@pytest.mark.parametrize(
    ("published_at", "expires_at", "field"),
    [
        (
            datetime(2026, 8, 24, 1, 0),
            _NOW + timedelta(days=1),
            "published_at",
        ),
        (
            _NOW,
            datetime(2026, 8, 25, 2, 0, tzinfo=timezone(timedelta(hours=1))),
            "expires_at",
        ),
    ],
)
def test_payload_builder_requires_explicit_utc_before_signing(
    tmp_path: Path,
    published_at: datetime,
    expires_at: datetime,
    field: str,
) -> None:
    artifact = _artifact(tmp_path, "windows-x86_64", "app.bin", b"artifact")

    with pytest.raises(ValueError, match=field):
        build_update_payload_bytes(
            sequence=1,
            channel="stable",
            version="1.0.0",
            published_at=published_at,
            expires_at=expires_at,
            release_notes_url="https://example.test/release",
            artifacts=(artifact,),
        )


def test_envelope_preserves_exact_payload_and_external_signature(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, "windows-x86_64", "app.bin", b"artifact")
    payload = build_update_payload_bytes(
        sequence=1,
        channel="stable",
        version="1.0.0",
        published_at=_NOW,
        expires_at=_NOW + timedelta(days=1),
        release_notes_url="https://example.test/release",
        artifacts=(artifact,),
    )
    signature = b"s" * 64

    encoded = assemble_signed_update_envelope(
        payload,
        key_id="release-2026",
        signature=signature,
    )
    document = json.loads(encoded)
    parsed = SignedUpdateEnvelope.from_dict(document)

    assert parsed.payload == payload
    assert parsed.signature == signature
    assert base64.b64decode(document["payload_base64"]) == payload


def test_envelope_rejects_wrong_signature_length(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, "windows-x86_64", "app.bin", b"artifact")
    payload = build_update_payload_bytes(
        sequence=1,
        channel="stable",
        version="1.0.0",
        published_at=_NOW,
        expires_at=_NOW + timedelta(days=1),
        release_notes_url="https://example.test/release",
        artifacts=(artifact,),
    )

    with pytest.raises(UpdateTrustError, match="invalid length"):
        assemble_signed_update_envelope(
            payload,
            key_id="release-2026",
            signature=b"short",
        )


def test_sha256sums_are_stable_sorted_and_not_a_signature(tmp_path: Path) -> None:
    zed = _artifact(tmp_path, "windows-x86_64", "z.bin", b"z")
    alpha = _artifact(tmp_path, "macos-aarch64", "a.bin", b"a")

    sums = build_sha256sums((zed, alpha)).decode().splitlines()

    assert sums[0].endswith("  a.bin")
    assert sums[1].endswith("  z.bin")
    assert all(len(line.split()[0]) == 64 for line in sums)


def test_sha256sums_reject_duplicate_public_filenames(tmp_path: Path) -> None:
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _artifact(first_dir, "windows-x86_64", "app.bin", b"one")
    second = _artifact(second_dir, "macos-aarch64", "app.bin", b"two")

    with pytest.raises(ValueError, match="filenames must be unique"):
        build_sha256sums((first, second))
