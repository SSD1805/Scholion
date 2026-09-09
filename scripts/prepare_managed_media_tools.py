from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_RELEASE_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SAFE_ASSET_RE = re.compile(r"^[A-Za-z0-9._-]{1,256}$")
_DOWNLOAD_TIMEOUT_SECONDS = 120
_TOOL_TIMEOUT_SECONDS = 15


class MediaToolPreparationError(RuntimeError):
    """Raised when reviewed media-tool custody cannot be reproduced safely."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_text(value: object, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise MediaToolPreparationError(f"{field} must be bounded non-empty text")
    if any(character in value for character in ("\n", "\r", "\x00")):
        raise MediaToolPreparationError(f"{field} must be one line")
    return value


def _require_sha(value: object, field: str) -> str:
    text = _require_text(value, field, 64)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise MediaToolPreparationError(f"{field} must be a lowercase 40-hex Git SHA")
    return text


def _require_digest(value: object, field: str) -> str:
    text = _require_text(value, field, 64)
    if _SHA256_RE.fullmatch(text) is None:
        raise MediaToolPreparationError(f"{field} must be lowercase SHA-256 hex")
    return text


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MediaToolPreparationError(
            "media-tool manifest is not readable JSON"
        ) from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise MediaToolPreparationError("unsupported media-tool manifest schema")
    if document.get("version_family") != "9.0":
        raise MediaToolPreparationError(
            "media-tool manifest must pin FFmpeg 9.0 family"
        )
    platforms = document.get("platforms")
    if not isinstance(platforms, dict):
        raise MediaToolPreparationError("media-tool manifest platforms are invalid")
    return document


def _platform_key() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows" and machine in {"amd64", "x86_64"}:
        return "windows-x86_64"
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    raise MediaToolPreparationError(
        f"managed release media tools are not qualified for {system}/{machine}"
    )


def _platform_config(manifest: Mapping[str, Any], key: str) -> dict[str, Any]:
    platforms = manifest.get("platforms")
    if not isinstance(platforms, dict):
        raise MediaToolPreparationError("media-tool manifest platforms are invalid")
    config = platforms.get(key)
    if not isinstance(config, dict):
        raise MediaToolPreparationError(f"media-tool manifest has no policy for {key}")
    return config


def _download_https(url: str, destination: Path) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise MediaToolPreparationError(
            "managed media-tool download must use github.com HTTPS"
        )
    request = urllib.request.Request(  # noqa: S310
        url,
        headers={"User-Agent": "Scholion-release-qualification"},
    )
    try:
        with (
            urllib.request.urlopen(  # noqa: S310
                request,
                timeout=_DOWNLOAD_TIMEOUT_SECONDS,
            ) as response,
            destination.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
    except OSError as exc:
        raise MediaToolPreparationError("managed media-tool download failed") from exc


def _copy_unique_zip_member(
    archive: zipfile.ZipFile,
    *,
    suffix: tuple[str, str],
    destination: Path,
) -> None:
    matches = []
    for name in archive.namelist():
        path = PurePosixPath(name)
        if len(path.parts) >= 2 and path.parts[-2:] == suffix:
            matches.append(name)
    if len(matches) != 1:
        raise MediaToolPreparationError(
            f"managed FFmpeg archive must contain exactly one {'/'.join(suffix)}"
        )
    with archive.open(matches[0], "r") as source, destination.open("wb") as output:
        shutil.copyfileobj(source, output)


def _prepare_windows(config: Mapping[str, Any], output: Path) -> dict[str, object]:
    if config.get("strategy") != "pinned-archive":
        raise MediaToolPreparationError(
            "Windows media-tool policy must use pinned archive"
        )
    if config.get("upstream_repository") != "BtbN/FFmpeg-Builds":
        raise MediaToolPreparationError("unexpected Windows media-tool upstream")
    release_tag = _require_text(config.get("release_tag"), "release_tag", 128)
    asset_name = _require_text(config.get("asset_name"), "asset_name", 256)
    if _SAFE_RELEASE_RE.fullmatch(release_tag) is None:
        raise MediaToolPreparationError("release_tag contains unsafe characters")
    if _SAFE_ASSET_RE.fullmatch(asset_name) is None or not asset_name.endswith(".zip"):
        raise MediaToolPreparationError("asset_name is not a safe ZIP name")
    expected_url = (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
        f"{release_tag}/{asset_name}"
    )
    if config.get("asset_url") != expected_url:
        raise MediaToolPreparationError("Windows media-tool asset URL is not canonical")
    expected_digest = _require_digest(config.get("asset_sha256"), "asset_sha256")
    expected_size = config.get("asset_size_bytes")
    if (
        not isinstance(expected_size, int)
        or isinstance(expected_size, bool)
        or expected_size < 1
    ):
        raise MediaToolPreparationError("asset_size_bytes must be positive")

    with tempfile.TemporaryDirectory(prefix="scholion-media-tools-") as temporary:
        archive_path = Path(temporary) / asset_name
        _download_https(expected_url, archive_path)
        if archive_path.stat().st_size != expected_size:
            raise MediaToolPreparationError(
                "managed FFmpeg archive size does not match policy"
            )
        if _sha256_file(archive_path) != expected_digest:
            raise MediaToolPreparationError(
                "managed FFmpeg archive digest does not match policy"
            )
        try:
            with zipfile.ZipFile(archive_path) as archive:
                _copy_unique_zip_member(
                    archive,
                    suffix=("bin", "ffmpeg.exe"),
                    destination=output / "ffmpeg.exe",
                )
                _copy_unique_zip_member(
                    archive,
                    suffix=("bin", "ffprobe.exe"),
                    destination=output / "ffprobe.exe",
                )
        except zipfile.BadZipFile as exc:
            raise MediaToolPreparationError(
                "managed FFmpeg archive is invalid"
            ) from exc

    return {
        "strategy": "pinned-archive",
        "upstream_repository": "BtbN/FFmpeg-Builds",
        "release_id": config.get("release_id"),
        "release_tag": release_tag,
        "asset_id": config.get("asset_id"),
        "asset_name": asset_name,
        "asset_sha256": expected_digest,
    }


def _resolved_command(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise MediaToolPreparationError(f"required build tool {name} is unavailable")
    return executable


def _run(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            list(command),
            cwd=cwd,
            capture_output=True,
            check=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise MediaToolPreparationError(
            f"managed media-tool build command failed: {Path(command[0]).name}"
        ) from exc


def _macos_policy(
    config: Mapping[str, Any],
) -> tuple[str, str, str, str, list[str]]:
    if config.get("strategy") != "source-build":
        raise MediaToolPreparationError("macOS media-tool policy must use source build")
    if config.get("upstream_repository") != "FFmpeg/FFmpeg":
        raise MediaToolPreparationError("unexpected macOS media-tool upstream")
    source_url = _require_text(config.get("source_url"), "source_url", 256)
    if source_url != "https://github.com/FFmpeg/FFmpeg.git":
        raise MediaToolPreparationError("macOS FFmpeg source URL is not canonical")
    tag = _require_text(config.get("tag"), "tag", 64)
    if tag != "n9.0":
        raise MediaToolPreparationError("macOS FFmpeg source tag is not approved")
    tag_object_sha = _require_sha(config.get("tag_object_sha"), "tag_object_sha")
    commit_sha = _require_sha(config.get("commit_sha"), "commit_sha")
    configure_args = _macos_configure_args(config.get("configure_args"))
    return source_url, tag, tag_object_sha, commit_sha, configure_args


def _macos_configure_args(raw_args: object) -> list[str]:
    if not isinstance(raw_args, list) or not raw_args:
        raise MediaToolPreparationError("macOS FFmpeg configure arguments are missing")
    configure_args: list[str] = []
    for index, raw in enumerate(raw_args):
        argument = _require_text(raw, f"configure_args[{index}]", 128)
        if not argument.startswith("--"):
            raise MediaToolPreparationError(
                "FFmpeg configure arguments must be options"
            )
        configure_args.append(argument)
    required_args = {"--disable-autodetect", "--disable-network", "--disable-shared"}
    if not required_args.issubset(configure_args):
        raise MediaToolPreparationError(
            "macOS FFmpeg build policy lost required hardening"
        )
    if any("gpl" in argument.lower() for argument in configure_args):
        raise MediaToolPreparationError(
            "macOS FFmpeg build must not enable GPL components"
        )
    return configure_args


def _prepare_macos(config: Mapping[str, Any], output: Path) -> dict[str, object]:
    source_url, tag, tag_object_sha, commit_sha, configure_args = _macos_policy(config)
    git = _resolved_command("git")
    make = _resolved_command("make")
    with tempfile.TemporaryDirectory(prefix="scholion-ffmpeg-source-") as temporary:
        source = Path(temporary) / "source"
        source.mkdir()
        _run([git, "init"], cwd=source)
        _run([git, "remote", "add", "origin", source_url], cwd=source)
        _run(
            [
                git,
                "fetch",
                "--depth",
                "1",
                "origin",
                f"refs/tags/{tag}:refs/tags/{tag}",
            ],
            cwd=source,
        )
        resolved_tag = _run(
            [git, "rev-parse", f"refs/tags/{tag}^{{tag}}"], cwd=source
        ).stdout.strip()
        resolved_commit = _run(
            [git, "rev-parse", f"refs/tags/{tag}^{{commit}}"], cwd=source
        ).stdout.strip()
        if resolved_tag != tag_object_sha or resolved_commit != commit_sha:
            raise MediaToolPreparationError(
                "FFmpeg source identity does not match reviewed policy"
            )
        _run([git, "checkout", "--detach", commit_sha], cwd=source)
        _run([str(source / "configure"), *configure_args], cwd=source)
        jobs = str(max(1, min(os.cpu_count() or 1, 4)))
        _run([make, f"-j{jobs}", "ffmpeg", "ffprobe"], cwd=source)
        for name in ("ffmpeg", "ffprobe"):
            built = source / name
            if not built.is_file():
                raise MediaToolPreparationError(
                    f"FFmpeg source build did not produce {name}"
                )
            shutil.copy2(built, output / name)
            (output / name).chmod(0o755)

    return {
        "strategy": "source-build",
        "upstream_repository": "FFmpeg/FFmpeg",
        "tag": tag,
        "tag_object_sha": tag_object_sha,
        "commit_sha": commit_sha,
        "configure_args": configure_args,
    }


def _tool_identity(path: Path, *, version_family: str) -> dict[str, object]:
    try:
        completed = subprocess.run(  # noqa: S603
            [str(path), "-version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=_TOOL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaToolPreparationError(
            f"prepared {path.name} could not execute"
        ) from exc
    if completed.returncode != 0 or not completed.stdout:
        raise MediaToolPreparationError(
            f"prepared {path.name} could not report identity"
        )
    first_line = completed.stdout.splitlines()[0]
    if len(first_line) > 256 or version_family not in first_line:
        raise MediaToolPreparationError(
            f"prepared {path.name} is outside reviewed FFmpeg version family"
        )
    return {
        "name": path.name,
        "version": first_line,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def prepare(manifest_path: Path, output: Path) -> bytes:
    manifest_path = manifest_path.resolve(strict=True)
    manifest = _load_manifest(manifest_path)
    key = _platform_key()
    config = _platform_config(manifest, key)
    if output.exists() and any(output.iterdir()):
        raise MediaToolPreparationError(
            "managed media-tool output directory must be empty"
        )
    output.mkdir(parents=True, exist_ok=True)

    if key == "windows-x86_64":
        source_identity = _prepare_windows(config, output)
        names = ("ffmpeg.exe", "ffprobe.exe")
    elif key == "macos-arm64":
        source_identity = _prepare_macos(config, output)
        names = ("ffmpeg", "ffprobe")
    else:  # pragma: no cover - _platform_key owns the closed platform set.
        raise MediaToolPreparationError(
            f"unsupported managed media-tool platform: {key}"
        )

    version_family = str(manifest["version_family"])
    evidence = {
        "schema_version": 1,
        "platform": key,
        "version_family": version_family,
        "manifest_sha256": _sha256_file(manifest_path),
        "license": _require_text(config.get("license"), "license", 64),
        "source": source_identity,
        "tools": sorted(
            (
                _tool_identity(output / name, version_family=version_family)
                for name in names
            ),
            key=lambda item: str(item["name"]),
        ),
    }
    payload = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "managed-media-tools.json").write_bytes(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the exact reviewed FFmpeg/FFprobe bytes for a Scholion package."
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("packaging/media-tools.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.manifest, arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
