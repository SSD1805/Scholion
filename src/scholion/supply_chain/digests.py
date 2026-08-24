from __future__ import annotations

from hashlib import sha256
from pathlib import Path

_READ_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one local file using bounded reads."""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
