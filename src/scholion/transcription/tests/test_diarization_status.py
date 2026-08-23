from importlib import metadata

from scholion.transcription.diarization_status import diarization_runtime_status


def _versions(values: dict[str, str]):
    def read(name: str) -> str:
        if name not in values:
            raise metadata.PackageNotFoundError(name)
        return values[name]

    return read


def test_status_reports_missing_optional_dependencies_without_importing_runtime() -> None:
    status = diarization_runtime_status(_versions({}))

    assert status.available is False
    assert status.reason_code == "dependencies_missing"
    assert status.message == "Speaker labeling is not installed in this local environment."


def test_status_fails_closed_for_unverifiable_or_security_held_lightning() -> None:
    unverified = diarization_runtime_status(
        _versions({"pyannote-audio": "4.0.7", "lightning": "2.7.0rc1"})
    )
    held = diarization_runtime_status(
        _versions({"pyannote-audio": "4.0.7", "lightning": "2.6.5"})
    )

    assert unverified.available is False
    assert unverified.reason_code == "dependency_unverified"
    assert "proven safe" in (unverified.message or "")
    assert held.available is False
    assert held.reason_code == "security_hold"
    assert "security requirement" in (held.message or "")


def test_status_reports_ready_only_after_dependency_floor_is_met() -> None:
    status = diarization_runtime_status(
        _versions({"pyannote-audio": "4.0.7", "lightning": "2.6.6"})
    )

    assert status.available is True
    assert status.reason_code is None
    assert status.message is None
