from __future__ import annotations

import re

_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


def validate_release_version(value: str) -> str:
    """Validate the bounded SemVer text used by first-release update metadata."""
    if len(value) > 128 or _SEMVER.fullmatch(value) is None:
        raise ValueError("release version must be valid semantic version text")
    return value
