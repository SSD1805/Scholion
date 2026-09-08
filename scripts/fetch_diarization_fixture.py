from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

_PYANNOTE_FIXTURE_COMMIT = "b749285c5cdd4636b2edc7f766f1352c8dde9369"
_BASE_URL = (
    "https://raw.githubusercontent.com/pyannote/pyannote-audio/"
    f"{_PYANNOTE_FIXTURE_COMMIT}/tests/data"
)
_FIXTURES = {
    "dev00.wav": {
        "size": 1_920_062,
        "git_blob": "1edcd0d599f715ffb64d859b2a46dfdd39d3507f",
    },
    "debug.development.rttm": {
        "size": 950,
        "git_blob": "472ce7ac0947b04e618a37f77421827c3a481089",
    },
}
_MAX_FIXTURE_BYTES = 3 * 1024 * 1024


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _fetch(name: str, output_dir: Path) -> Path:
    expected = _FIXTURES[name]
    request = Request(  # noqa: S310
        f"{_BASE_URL}/{name}",
        headers={"User-Agent": "Scholion-diarization-acceptance/1"},
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310
        payload = response.read(_MAX_FIXTURE_BYTES + 1)
    if len(payload) > _MAX_FIXTURE_BYTES:
        raise RuntimeError(f"pinned diarization fixture {name} exceeded the byte ceiling")
    if len(payload) != expected["size"]:
        raise RuntimeError(f"pinned diarization fixture {name} changed size")
    if _git_blob_sha1(payload) != expected["git_blob"]:
        raise RuntimeError(f"pinned diarization fixture {name} changed identity")
    path = output_dir / name
    path.write_bytes(payload)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and verify pyannote's pinned two-speaker acceptance fixture."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.expanduser().resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in _FIXTURES:
        print(_fetch(name, output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
