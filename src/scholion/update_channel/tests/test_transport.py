from __future__ import annotations

import io
from pathlib import Path

import pytest

from scholion.update_channel import service
from scholion.update_channel.service import HttpsUpdateTransport, UpdateChannelError


class _Response:
    def __init__(
        self, content: bytes, *, url: str = "https://example.test/final"
    ) -> None:
        self._stream = io.BytesIO(content)
        self._url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url


class _Urlopen:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[object, float]] = []

    def __call__(self, request: object, *, timeout: float) -> _Response:
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected network call")
        return self.responses.pop(0)


def _patch_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    *responses: _Response,
) -> _Urlopen:
    opener = _Urlopen(list(responses))
    monkeypatch.setattr(service, "urlopen", opener)
    return opener


def test_fetch_manifest_accepts_bounded_https_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = _patch_urlopen(
        monkeypatch,
        _Response(b'{"schema_version":1}'),
    )
    transport = HttpsUpdateTransport(timeout_seconds=3.5)

    result = transport.fetch_manifest("https://example.test/manifest.json")

    assert result == {"schema_version": 1}
    assert len(opener.calls) == 1
    assert opener.calls[0][1] == 3.5


def test_fetch_manifest_rejects_non_https_input_or_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = HttpsUpdateTransport()

    with pytest.raises(UpdateChannelError, match="HTTPS"):
        transport.fetch_manifest("http://example.test/manifest.json")

    _patch_urlopen(
        monkeypatch,
        _Response(b"{}", url="http://example.test/downgraded"),
    )
    with pytest.raises(UpdateChannelError, match="HTTPS"):
        transport.fetch_manifest("https://example.test/manifest.json")


def test_fetch_manifest_rejects_oversized_invalid_or_non_object_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = HttpsUpdateTransport()

    _patch_urlopen(
        monkeypatch,
        _Response(b"x" * (service._MAX_MANIFEST_BYTES + 1)),
    )
    with pytest.raises(UpdateChannelError, match="safe size"):
        transport.fetch_manifest("https://example.test/manifest.json")

    _patch_urlopen(monkeypatch, _Response(b"not-json"))
    with pytest.raises(UpdateChannelError, match="valid JSON"):
        transport.fetch_manifest("https://example.test/manifest.json")

    _patch_urlopen(monkeypatch, _Response(b"[]"))
    with pytest.raises(UpdateChannelError, match="JSON object"):
        transport.fetch_manifest("https://example.test/manifest.json")


def test_stage_verified_artifact_commits_exact_signed_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = b"trusted-update-bytes"
    expected_hash = service.sha256(content).hexdigest()
    _patch_urlopen(monkeypatch, _Response(content))
    destination = tmp_path / "private" / "release.bin"

    HttpsUpdateTransport().stage_verified_artifact(
        "https://example.test/release.bin",
        destination=destination,
        expected_size=len(content),
        expected_sha256=expected_hash,
    )

    assert destination.read_bytes() == content
    assert tuple(destination.parent.iterdir()) == (destination,)


def test_stage_rejects_short_oversized_or_hash_mismatching_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    transport = HttpsUpdateTransport()
    destination = tmp_path / "stage" / "release.bin"

    _patch_urlopen(monkeypatch, _Response(b"short"))
    with pytest.raises(UpdateChannelError, match="size did not match"):
        transport.stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=10,
            expected_sha256="a" * 64,
        )
    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []

    _patch_urlopen(monkeypatch, _Response(b"too-long"))
    with pytest.raises(UpdateChannelError, match="exceeded its signed size"):
        transport.stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=3,
            expected_sha256="a" * 64,
        )
    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []

    content = b"right-size"
    _patch_urlopen(monkeypatch, _Response(content))
    with pytest.raises(UpdateChannelError, match="hash did not match"):
        transport.stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=len(content),
            expected_sha256="0" * 64,
        )
    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_stage_rejects_bad_signed_metadata_before_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    opener = _patch_urlopen(monkeypatch)
    transport = HttpsUpdateTransport()
    destination = tmp_path / "release.bin"

    with pytest.raises(UpdateChannelError, match="HTTPS"):
        transport.stage_verified_artifact(
            "http://example.test/release.bin",
            destination=destination,
            expected_size=1,
            expected_sha256="a" * 64,
        )
    with pytest.raises(UpdateChannelError, match="size must be positive"):
        transport.stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=0,
            expected_sha256="a" * 64,
        )
    with pytest.raises(UpdateChannelError, match="hash is invalid"):
        transport.stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=1,
            expected_sha256="not-a-hash",
        )
    assert opener.calls == []


def test_stage_rejects_https_to_http_redirect_and_cleans_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = b"trusted-update-bytes"
    _patch_urlopen(
        monkeypatch,
        _Response(content, url="http://example.test/release.bin"),
    )
    destination = tmp_path / "stage" / "release.bin"

    with pytest.raises(UpdateChannelError, match="HTTPS"):
        HttpsUpdateTransport().stage_verified_artifact(
            "https://example.test/release.bin",
            destination=destination,
            expected_size=len(content),
            expected_sha256=service.sha256(content).hexdigest(),
        )

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_transport_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        HttpsUpdateTransport(timeout_seconds=0)
