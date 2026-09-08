from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

from scholion.transcription.diarization import PyannoteSpeakerDiarizer
from scholion.transcription.speaker_models import SpeakerDiarizationResult

_MIN_REFERENCE_MATCH = 0.45


@dataclass(frozen=True, slots=True)
class _ReferenceTurn:
    start_seconds: float
    end_seconds: float
    speaker: str


def _reference_turns(audio_path: Path, rttm_path: Path) -> tuple[_ReferenceTurn, ...]:
    turns: list[_ReferenceTurn] = []
    for line_number, raw_line in enumerate(
        rttm_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 8 or fields[0] != "SPEAKER":
            raise RuntimeError(f"invalid RTTM reference line {line_number}")
        if fields[1] != audio_path.stem:
            continue
        try:
            start = float(fields[3])
            duration = float(fields[4])
        except ValueError as exc:
            raise RuntimeError(
                f"invalid RTTM timing on line {line_number}"
            ) from exc
        if start < 0 or duration <= 0:
            raise RuntimeError(f"invalid RTTM interval on line {line_number}")
        turns.append(
            _ReferenceTurn(
                start_seconds=start,
                end_seconds=start + duration,
                speaker=fields[7],
            )
        )
    if not turns:
        raise RuntimeError("RTTM reference contains no turns for the acceptance audio")
    speakers = {turn.speaker for turn in turns}
    if len(speakers) != 2:
        raise RuntimeError("pinned diarization reference must contain exactly two speakers")
    has_overlap = any(
        first.speaker != second.speaker
        and _overlap(
            first.start_seconds,
            first.end_seconds,
            second.start_seconds,
            second.end_seconds,
        )
        > 0
        for index, first in enumerate(turns)
        for second in turns[index + 1 :]
    )
    if not has_overlap:
        raise RuntimeError("pinned diarization reference must exercise overlapping speech")
    return tuple(turns)


def _overlap(first_start: float, first_end: float, second_start: float, second_end: float) -> float:
    return max(0.0, min(first_end, second_end) - max(first_start, second_start))


def _reference_match(
    result: SpeakerDiarizationResult,
    reference: tuple[_ReferenceTurn, ...],
) -> float:
    predicted_speakers = sorted({turn.speaker_ref for turn in result.turns})
    reference_speakers = sorted({turn.speaker for turn in reference})
    if len(predicted_speakers) != 2 or len(reference_speakers) != 2:
        return 0.0

    best_overlap = 0.0
    for assignment in permutations(reference_speakers):
        mapping = dict(zip(predicted_speakers, assignment, strict=True))
        overlap_seconds = sum(
            _overlap(
                predicted.start_seconds,
                predicted.end_seconds,
                expected.start_seconds,
                expected.end_seconds,
            )
            for predicted in result.turns
            for expected in reference
            if mapping[predicted.speaker_ref] == expected.speaker
        )
        best_overlap = max(best_overlap, overlap_seconds)
    reference_seconds = sum(
        turn.end_seconds - turn.start_seconds for turn in reference
    )
    return best_overlap / reference_seconds


def _validate_result(
    *,
    audio_path: Path,
    result: SpeakerDiarizationResult,
    reference: tuple[_ReferenceTurn, ...],
) -> None:
    if not result.turns:
        raise RuntimeError("real diarization acceptance produced no speaker turns")
    if result.provenance.telemetry_enabled:
        raise RuntimeError("diarization acceptance unexpectedly enabled telemetry")
    if result.provenance.provider != "pyannote.audio":
        raise RuntimeError("diarization acceptance returned unexpected provenance")
    speakers = {turn.speaker_ref for turn in result.turns}
    if len(speakers) != 2:
        raise RuntimeError("real diarization acceptance did not recover two speakers")
    for turn in result.turns:
        if not turn.speaker_ref.startswith("speaker-"):
            raise RuntimeError("diarization acceptance returned a non-anonymous label")
        if turn.start_seconds < 0 or turn.end_seconds <= turn.start_seconds:
            raise RuntimeError("diarization acceptance returned an invalid turn")
    match = _reference_match(result, reference)
    if match < _MIN_REFERENCE_MATCH:
        raise RuntimeError(
            "real diarization acceptance did not match enough pinned speaker evidence"
        )
    print(
        f"accepted {audio_path.name}: {len(result.turns)} turns, "
        f"{len(speakers)} speakers, reference_match={match:.3f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run gated real pyannote Community-1 inference against a two-speaker "
            "ground-truth fixture and prove local-cache reopen semantics."
        )
    )
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--reference-rttm", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    arguments = parser.parse_args()

    audio_path = arguments.audio_path.expanduser().resolve(strict=True)
    reference_path = arguments.reference_rttm.expanduser().resolve(strict=True)
    reference = _reference_turns(audio_path, reference_path)
    cache_dir = arguments.cache_dir.expanduser().resolve(strict=False)
    if not os.environ.get("HF_TOKEN") and not os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        raise RuntimeError(
            "real diarization acceptance requires an authenticated Hugging Face token"
        )

    diarizer = PyannoteSpeakerDiarizer(model_cache_path=cache_dir)
    downloaded = diarizer.diarize(audio_path, allow_model_download=True)
    _validate_result(audio_path=audio_path, result=downloaded, reference=reference)

    cached = diarizer.diarize(audio_path, allow_model_download=False)
    _validate_result(audio_path=audio_path, result=cached, reference=reference)
    return 0


if __name__ == "__main__":
    sys.exit(main())
