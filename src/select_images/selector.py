"""Burst-photo grouping and best-image selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2

from .image_io import LoadedImage, iter_image_files, load_image
from .scoring import QualityScore, score_image


@dataclass(frozen=True)
class ImageCandidate:
    """A photo and its computed quality score."""

    path: Path
    score: QualityScore
    timestamp: float


@dataclass(frozen=True)
class SelectionResult:
    """The winner chosen from one burst group."""

    winner: ImageCandidate
    rejected: tuple[ImageCandidate, ...]

    @property
    def group(self) -> tuple[ImageCandidate, ...]:
        return (self.winner, *self.rejected)


def select_best_images(
    input_dir: Path,
    *,
    recursive: bool = False,
    burst_window_seconds: float = 2.0,
    output_dir: Path | None = None,
) -> list[SelectionResult]:
    """Select the best image from every burst group in a directory.

    Photos are grouped by EXIF capture time when available and by filesystem
    modification time otherwise. Each group contains neighboring photos captured
    within ``burst_window_seconds`` seconds of the previous photo.
    """

    candidates = [_candidate_from_path(path) for path in iter_image_files(input_dir, recursive)]
    groups = _group_candidates(candidates, burst_window_seconds)
    results = [_select_group_winner(group) for group in groups]

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for result in results:
            copy2(result.winner.path, output_dir / result.winner.path.name)
    return results


def _candidate_from_path(path: Path) -> ImageCandidate:
    loaded = load_image(path)
    timestamp = loaded.timestamp if loaded.timestamp is not None else path.stat().st_mtime
    return ImageCandidate(path=path, score=score_image(loaded), timestamp=timestamp)


def _group_candidates(
    candidates: list[ImageCandidate], burst_window_seconds: float
) -> list[tuple[ImageCandidate, ...]]:
    if not candidates:
        return []

    ordered = sorted(candidates, key=lambda candidate: (candidate.timestamp, candidate.path.name))
    groups: list[list[ImageCandidate]] = [[ordered[0]]]
    for candidate in ordered[1:]:
        previous = groups[-1][-1]
        if candidate.timestamp - previous.timestamp <= burst_window_seconds:
            groups[-1].append(candidate)
        else:
            groups.append([candidate])
    return [tuple(group) for group in groups]


def _select_group_winner(group: tuple[ImageCandidate, ...]) -> SelectionResult:
    winner = max(group, key=lambda candidate: (candidate.score.total, candidate.score.sharpness))
    rejected = tuple(candidate for candidate in group if candidate != winner)
    return SelectionResult(winner=winner, rejected=rejected)
