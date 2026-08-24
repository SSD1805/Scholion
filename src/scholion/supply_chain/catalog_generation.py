from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from scholion.supply_chain.model_trust import TrustedModelFile, TrustedModelSpec

_READ_CHUNK_BYTES = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_trusted_model_spec(
    *,
    model_id: str,
    engine: str,
    repository_id: str,
    revision: str,
    source_url: str,
    license_id: str,
    license_url: str,
    snapshot_root: Path,
    cache_root: Path,
) -> TrustedModelSpec:
    """Measure one deliberately selected immutable snapshot into policy material.

    This function does not decide that a model is trustworthy. It deterministically records
    the exact file set the reviewer selected so the resulting entry can be reviewed in a
    normal repository change before it is bundled in a signed Scholion release.
    """
    resolved_cache = cache_root.expanduser().resolve(strict=True)
    resolved_snapshot = snapshot_root.expanduser().resolve(strict=True)
    if not resolved_snapshot.is_dir() or not resolved_snapshot.is_relative_to(
        resolved_cache
    ):
        raise ValueError("reviewed model snapshot must be inside the supplied cache root")
    if resolved_snapshot.name != revision:
        raise ValueError("reviewed snapshot directory must match the immutable revision")

    files: list[TrustedModelFile] = []
    for candidate in sorted(
        (path for path in resolved_snapshot.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(resolved_snapshot).as_posix(),
    ):
        resolved_candidate = candidate.resolve(strict=True)
        if not resolved_candidate.is_relative_to(resolved_cache):
            raise ValueError("reviewed model file resolves outside the supplied cache root")
        relative = candidate.relative_to(resolved_snapshot).as_posix()
        files.append(
            TrustedModelFile(
                path=relative,
                size_bytes=candidate.stat().st_size,
                sha256_hex=_sha256(candidate),
            )
        )
    if not files:
        raise ValueError("reviewed model snapshot contains no files")

    return TrustedModelSpec(
        model_id=model_id,
        engine=engine,
        repository_id=repository_id,
        revision=revision,
        source_url=source_url,
        license_id=license_id,
        license_url=license_url,
        files=tuple(files),
    )
