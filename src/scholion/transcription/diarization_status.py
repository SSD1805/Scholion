"""Cheap local availability check for the optional diarization runtime.

This probe deliberately avoids importing pyannote or loading model checkpoints. It exists so
consumer surfaces can refuse an unavailable or security-held capability before a long-running
job is launched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata
from typing import Callable

VersionReader = Callable[[str], str]

_MINIMUM_SAFE_LIGHTNING = (2, 6, 6)
_STABLE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.post\d+)?$")


@dataclass(frozen=True, slots=True)
class DiarizationRuntimeStatus:
    """Public capability state safe to expose without local paths or package internals."""

    available: bool
    reason_code: str | None
    message: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "reason_code": self.reason_code,
            "message": self.message,
        }


def diarization_runtime_status(
    version_reader: VersionReader = metadata.version,
) -> DiarizationRuntimeStatus:
    """Return whether speaker labeling can be offered in the current local runtime."""

    try:
        version_reader("pyannote-audio")
        lightning_version = version_reader("lightning")
    except metadata.PackageNotFoundError:
        return DiarizationRuntimeStatus(
            available=False,
            reason_code="dependencies_missing",
            message="Speaker labeling is not installed in this local environment.",
        )

    match = _STABLE_VERSION.fullmatch(lightning_version)
    if match is None:
        return DiarizationRuntimeStatus(
            available=False,
            reason_code="dependency_unverified",
            message=(
                "Speaker labeling is unavailable because a local dependency cannot be "
                "proven safe for model loading."
            ),
        )

    parsed = tuple(int(component) for component in match.groups())
    if parsed < _MINIMUM_SAFE_LIGHTNING:
        return DiarizationRuntimeStatus(
            available=False,
            reason_code="security_hold",
            message=(
                "Speaker labeling is temporarily unavailable because a local dependency "
                "does not meet Scholion's security requirement."
            ),
        )

    return DiarizationRuntimeStatus(
        available=True,
        reason_code=None,
        message=None,
    )
