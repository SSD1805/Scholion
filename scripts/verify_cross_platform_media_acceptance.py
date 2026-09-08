from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib import request

from verify_engine_acceptance import (
    _environment,
    _initialize,
    _install_tiny,
    _load_canonical,
    _run,
    _transcribe,
    _validate_contract,
    _validate_exports,
    _validate_private_cleanup,
    _validate_privacy,
    _validate_timestamps,
    _wrap_media,
)

# OpenAI Whisper's own known-speech test fixture, pinned to an immutable commit.
# The Git blob identity and exact byte size come from that pinned repository tree.
_JFK_FIXTURE_URL = (
    "https://raw.githubusercontent.com/openai/whisper/"
    "86098128c0b4f24f0e2aa2994de830614b474227/tests/jfk.flac"
)
_JFK_FIXTURE_GIT_BLOB = "e44b7c13897eae7f78beb220c61fe77429a3961d"
_JFK_FIXTURE_SIZE = 1_152_693
_JFK_WORDS = frozenset({"fellow", "americans", "country", "ask", "you"})
_MIN_JFK_WORDS = 3
_MAX_FIXTURE_BYTES = 2 * 1024 * 1024


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _fetch_public_fixture(root: Path) -> Path:
    fixture_request = request.Request(  # noqa: S310
        _JFK_FIXTURE_URL,
        headers={"User-Agent": "Scholion-acceptance/1"},
    )
    with request.urlopen(fixture_request, timeout=60) as response:  # noqa: S310
        payload = response.read(_MAX_FIXTURE_BYTES + 1)
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise RuntimeError("public acceptance fixture exceeded the byte ceiling")
    if len(payload) != _JFK_FIXTURE_SIZE:
        raise RuntimeError("public acceptance fixture size changed unexpectedly")
    if _git_blob_sha1(payload) != _JFK_FIXTURE_GIT_BLOB:
        raise RuntimeError("public acceptance fixture identity changed unexpectedly")
    path = root / "jfk-upstream.flac"
    path.write_bytes(payload)
    return path


def _canonical_wav(root: Path, source: Path) -> Path:
    output = root / "jfk-canonical.wav"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ]
    )
    return output


def _compress_mp3(root: Path, audio: Path, *, name: str) -> Path:
    output = root / name
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(audio),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "96k",
            str(output),
        ]
    )
    return output


def _longer_mp3(root: Path, audio: Path) -> Path:
    repeated = root / "jfk-repeated.wav"
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(audio),
            "-i",
            str(audio),
            "-i",
            str(audio),
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(repeated),
        ]
    )
    return _compress_mp3(root, repeated, name="jfk-repeated.mp3")


def _ffprobe(path: Path) -> dict[str, Any]:
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,format_name",
            "-show_entries",
            "stream=index,codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("ffprobe acceptance result is not a JSON object")
    return payload


def _duration_seconds(path: Path) -> float:
    probe = _ffprobe(path)
    raw_format = probe.get("format")
    if not isinstance(raw_format, dict):
        raise RuntimeError("ffprobe acceptance result omitted format metadata")
    duration = float(raw_format.get("duration", 0.0))
    if duration <= 0:
        raise RuntimeError("acceptance media reported a non-positive duration")
    return duration


def _expected_audio_stream_index(path: Path) -> int:
    streams = _ffprobe(path).get("streams")
    if not isinstance(streams, list):
        raise RuntimeError("ffprobe acceptance result omitted stream metadata")
    audio_indices = [
        int(stream["index"])
        for stream in streams
        if isinstance(stream, dict)
        and stream.get("codec_type") == "audio"
        and "index" in stream
    ]
    if len(audio_indices) != 1:
        raise RuntimeError(
            "acceptance media must contain exactly one discoverable audio stream"
        )
    return audio_indices[0]


def _offline_environment(root: Path, output_dir: Path) -> dict[str, str]:
    env = _environment(root, output_dir)
    env.update(
        {
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    return env


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_source_identity(output_dir: Path, input_path: Path) -> None:
    document, _ = _load_canonical(output_dir)
    source = document.get("source")
    if not isinstance(source, dict):
        raise RuntimeError("canonical transcript omitted source provenance")
    if source.get("sha256") != _sha256(input_path):
        raise RuntimeError("canonical transcript recorded the wrong source hash")
    if int(source.get("size_bytes", -1)) != input_path.stat().st_size:
        raise RuntimeError("canonical transcript recorded the wrong source size")
    expected_stream = _expected_audio_stream_index(input_path)
    if int(source.get("audio_stream_index", -1)) != expected_stream:
        raise RuntimeError("canonical transcript recorded the wrong audio stream")


def _words(text: str) -> set[str]:
    return {
        "".join(character for character in token.lower() if character.isalpha())
        for token in text.split()
        if token.strip()
    }


def _validate_jfk(
    output_dir: Path,
    *,
    input_path: Path,
    model_dir: Path,
    expected_revision: str,
    expected_decode_strategy: str,
) -> set[str]:
    document, raw_document = _load_canonical(output_dir)
    recognized = _words(str(document.get("text", ""))) & _JFK_WORDS
    if len(recognized) < _MIN_JFK_WORDS:
        raise RuntimeError(
            f"public known-speech recognition too weak: matched {sorted(recognized)}"
        )
    _validate_contract(
        document,
        expected_decode_strategy=expected_decode_strategy,
        expected_revision=expected_revision,
        expect_enhancement=False,
    )
    _validate_timestamps(document)
    _validate_privacy(raw_document, input_path=input_path, model_dir=model_dir)
    _validate_exports(output_dir)
    _validate_source_identity(output_dir, input_path)
    return recognized


def _run_case(
    *,
    root: Path,
    model_dir: Path,
    input_path: Path,
    output_name: str,
    revision: str,
    decode_strategy: str,
) -> set[str]:
    output_dir = root / output_name
    _transcribe(input_path, env=_offline_environment(root, output_dir))
    return _validate_jfk(
        output_dir,
        input_path=input_path,
        model_dir=model_dir,
        expected_revision=revision,
        expected_decode_strategy=decode_strategy,
    )


def verify_public_media() -> None:
    with tempfile.TemporaryDirectory(prefix="scholion-public-media-") as temporary:
        root = Path(temporary).resolve()
        model_dir = root / "cache" / "models"

        upstream_flac = _fetch_public_fixture(root)
        canonical_wav = _canonical_wav(root, upstream_flac)
        compressed_mp3 = _compress_mp3(
            root, canonical_wav, name="jfk-compressed.mp3"
        )
        video_mp4 = _wrap_media(root, canonical_wav)
        longer_mp3 = _longer_mp3(root, canonical_wav)

        if compressed_mp3.stat().st_size >= canonical_wav.stat().st_size:
            raise RuntimeError("MP3 acceptance derivative is not actually compressed")
        if longer_mp3.stat().st_size <= compressed_mp3.stat().st_size:
            raise RuntimeError("long acceptance derivative did not grow in byte size")
        if _duration_seconds(longer_mp3) <= _duration_seconds(compressed_mp3) * 2.5:
            raise RuntimeError("long acceptance derivative did not grow in duration")

        setup_env = _environment(root, root / "output-setup")
        _initialize(setup_env)
        revision = _install_tiny(setup_env)

        cases = (
            (upstream_flac, "output-upstream-flac", "ffmpeg_normalize"),
            (canonical_wav, "output-canonical-wav", "direct"),
            (compressed_mp3, "output-compressed-mp3", "ffmpeg_normalize"),
            (video_mp4, "output-video-mp4", "ffmpeg_normalize"),
            (longer_mp3, "output-long-mp3", "ffmpeg_normalize"),
        )
        observed: dict[str, set[str]] = {}
        for input_path, output_name, strategy in cases:
            observed[output_name] = _run_case(
                root=root,
                model_dir=model_dir,
                input_path=input_path,
                output_name=output_name,
                revision=revision,
                decode_strategy=strategy,
            )

        baseline = observed["output-canonical-wav"]
        for label, words in observed.items():
            if len(baseline & words) < _MIN_JFK_WORDS:
                raise RuntimeError(
                    f"{label} changed public known-speech recognition too much"
                )

        if not model_dir.is_dir() or not any(model_dir.iterdir()):
            raise RuntimeError("managed model install did not populate private cache")
        _validate_private_cleanup(root)


if __name__ == "__main__":
    for executable in ("ffmpeg", "ffprobe"):
        if shutil.which(executable) is None:
            raise SystemExit(
                f"required acceptance executable unavailable: {executable}"
            )
    verify_public_media()
