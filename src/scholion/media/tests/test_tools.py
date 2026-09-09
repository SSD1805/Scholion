from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scholion.media.errors import MediaToolUnavailableError
from scholion.media.tools import media_tool_identity, resolve_media_tool


def _bundled_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _freeze(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(root), raising=False)


def test_source_runtime_resolves_media_tool_from_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    seen: list[str] = []

    def fake_which(name: str) -> str:
        seen.append(name)
        return f"/developer-tools/{name}"

    monkeypatch.setattr(shutil, "which", fake_which)

    executable = resolve_media_tool("ffmpeg")

    assert executable.endswith(_bundled_name("ffmpeg"))
    assert seen == [_bundled_name("ffmpeg")]


def test_frozen_runtime_uses_only_bundled_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    tool = bundle / "media-tools" / _bundled_name("ffprobe")
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"managed-ffprobe")
    _freeze(monkeypatch, bundle)

    def reject_path(_: str) -> None:
        raise AssertionError("frozen runtime must not consult PATH")

    monkeypatch.setattr(shutil, "which", reject_path)

    assert resolve_media_tool("ffprobe") == str(tool.resolve())


def test_frozen_runtime_fails_closed_when_bundled_tool_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _freeze(monkeypatch, bundle)
    monkeypatch.setattr(shutil, "which", lambda _: "/host/ffmpeg")

    with pytest.raises(MediaToolUnavailableError, match="missing managed ffmpeg"):
        resolve_media_tool("ffmpeg")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation is not guaranteed")
def test_frozen_runtime_rejects_media_tool_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    media_tools = bundle / "media-tools"
    media_tools.mkdir(parents=True)
    outside = tmp_path / _bundled_name("ffmpeg")
    outside.write_bytes(b"outside")
    (media_tools / _bundled_name("ffmpeg")).symlink_to(outside)
    _freeze(monkeypatch, bundle)

    with pytest.raises(MediaToolUnavailableError, match="outside its bundle"):
        resolve_media_tool("ffmpeg")


def test_media_tool_identity_is_bounded_and_does_not_expose_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    tool = bundle / "media-tools" / _bundled_name("ffmpeg")
    tool.parent.mkdir(parents=True)
    payload = b"exact-managed-ffmpeg-bytes"
    tool.write_bytes(payload)
    _freeze(monkeypatch, bundle)

    def fake_run(*_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout="ffmpeg version 9.0 Copyright FFmpeg\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    identity = media_tool_identity("ffmpeg")

    assert identity.name == "ffmpeg"
    assert identity.source == "bundled"
    assert identity.version == "ffmpeg version 9.0 Copyright FFmpeg"
    assert identity.size_bytes == len(payload)
    assert identity.sha256 == hashlib.sha256(payload).hexdigest()
    assert str(bundle) not in repr(identity)


def test_media_tool_identity_rejects_failed_and_unbounded_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    tool = bundle / "media-tools" / _bundled_name("ffmpeg")
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"managed")
    _freeze(monkeypatch, bundle)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="failed"
        ),
    )
    with pytest.raises(MediaToolUnavailableError, match="could not be executed"):
        media_tool_identity("ffmpeg")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="x" * 257, stderr=""
        ),
    )
    with pytest.raises(MediaToolUnavailableError, match="invalid version identity"):
        media_tool_identity("ffmpeg")


def test_media_tool_resolver_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unsupported media tool"):
        resolve_media_tool("curl")
