"""Photo quality scoring for burst-shot selection."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from .image_io import LoadedImage


@dataclass(frozen=True)
class QualityScore:
    """Breakdown of a photo quality score."""

    total: float
    sharpness: float
    exposure: float
    contrast: float
    saturation: float
    resolution: float


def score_image(image: LoadedImage) -> QualityScore:
    """Score a loaded image on a 0..100-ish scale.

    The model is intentionally transparent: sharp burst photos with balanced
    exposure, contrast, color, and adequate resolution rise to the top.
    """

    luminance = _luminance_values(image)
    sharpness = _sharpness_score(luminance, image.width, image.height)
    exposure = _exposure_score(luminance)
    contrast = _contrast_score(luminance)
    saturation = _saturation_score(image.pixels)
    resolution = _resolution_score(image.width, image.height)

    total = (
        sharpness * 0.42
        + exposure * 0.24
        + contrast * 0.16
        + saturation * 0.08
        + resolution * 0.10
    )
    return QualityScore(
        total=round(total, 3),
        sharpness=round(sharpness, 3),
        exposure=round(exposure, 3),
        contrast=round(contrast, 3),
        saturation=round(saturation, 3),
        resolution=round(resolution, 3),
    )


def _luminance_values(image: LoadedImage) -> list[float]:
    return [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in image.pixels]


def _sharpness_score(luminance: list[float], width: int, height: int) -> float:
    if width < 3 or height < 3:
        return 0.0

    laplacian_values: list[float] = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = luminance[row + x]
            laplacian = (
                4 * center
                - luminance[row + x - 1]
                - luminance[row + x + 1]
                - luminance[row - width + x]
                - luminance[row + width + x]
            )
            laplacian_values.append(laplacian)

    variance = _variance(laplacian_values)
    return _clamp((variance / 1200) * 100)


def _exposure_score(luminance: list[float]) -> float:
    if not luminance:
        return 0.0
    mean = fmean(luminance)
    distance_penalty = abs(mean - 128) / 128
    clipped_ratio = sum(1 for value in luminance if value <= 5 or value >= 250) / len(luminance)
    return _clamp(100 * (1 - distance_penalty) - clipped_ratio * 85)


def _contrast_score(luminance: list[float]) -> float:
    if not luminance:
        return 0.0
    stddev = _variance(luminance) ** 0.5
    return _clamp((stddev / 64) * 100)


def _saturation_score(pixels: tuple[tuple[int, int, int], ...]) -> float:
    if not pixels:
        return 0.0
    saturations = []
    for red, green, blue in pixels:
        maximum = max(red, green, blue)
        minimum = min(red, green, blue)
        saturations.append(0.0 if maximum == 0 else (maximum - minimum) / maximum)
    mean_saturation = fmean(saturations)
    if mean_saturation <= 0.35:
        return _clamp((mean_saturation / 0.35) * 100)
    return _clamp(100 - ((mean_saturation - 0.35) / 0.65) * 25)


def _resolution_score(width: int, height: int) -> float:
    megapixels = (width * height) / 1_000_000
    return _clamp((megapixels / 8) * 100)


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = fmean(values)
    return fmean([(value - mean) ** 2 for value in values])


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))
