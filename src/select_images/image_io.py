"""Image loading helpers.

The production path uses Pillow for common photo formats. A tiny PPM reader is
kept dependency-free so the scoring logic can be tested in minimal environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".ppm",
}


@dataclass(frozen=True)
class LoadedImage:
    """Simple RGB image container used by the scorer."""

    width: int
    height: int
    pixels: tuple[tuple[int, int, int], ...]
    timestamp: float | None = None


def iter_image_files(directory: Path, recursive: bool = False) -> Iterable[Path]:
    """Yield supported image files in a stable order."""

    pattern = "**/*" if recursive else "*"
    for path in sorted(directory.glob(pattern)):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def load_image(path: Path) -> LoadedImage:
    """Load an image as RGB pixels.

    Pillow is required for real-world JPEG/PNG photos. Plain PPM (P3/P6) files
    are supported directly for tests and simple fixtures.
    """

    if path.suffix.lower() == ".ppm":
        return _load_ppm(path)
    return _load_with_pillow(path)


def _load_with_pillow(path: Path) -> LoadedImage:
    if find_spec("PIL") is None:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Pillow is required for JPEG/PNG/TIFF/WebP input. "
            "Install with: python -m pip install Pillow"
        )

    from PIL import Image, ExifTags

    with Image.open(path) as image:
        timestamp = _timestamp_from_exif(image, ExifTags)
        rgb = image.convert("RGB")
        width, height = rgb.size
        pixels = tuple(rgb.getdata())
    return LoadedImage(width=width, height=height, pixels=pixels, timestamp=timestamp)


def _timestamp_from_exif(image: object, exif_tags: object) -> float | None:
    try:
        exif = image.getexif()
    except Exception:  # pragma: no cover - defensive for malformed metadata
        return None
    if not exif:
        return None

    tag_names = getattr(exif_tags, "TAGS", {})
    date_value: str | None = None
    for tag_id, value in exif.items():
        if tag_names.get(tag_id) in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}:
            date_value = str(value)
            break
    if not date_value:
        return None

    from datetime import datetime

    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_value, fmt).timestamp()
        except ValueError:
            continue
    return None


def _load_ppm(path: Path) -> LoadedImage:
    data = path.read_bytes()
    tokens = list(_ppm_tokens(data))
    if len(tokens) < 4:
        raise ValueError(f"Invalid PPM file: {path}")
    magic = tokens[0]
    if magic not in {b"P3", b"P6"}:
        raise ValueError(f"Unsupported PPM type {magic!r}: {path}")

    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if width <= 0 or height <= 0 or max_value <= 0:
        raise ValueError(f"Invalid PPM dimensions or max value: {path}")

    expected_values = width * height * 3
    if magic == b"P3":
        values = [int(token) for token in tokens[4:]]
    else:
        header_length = _ppm_header_length(data, 4)
        values = list(data[header_length : header_length + expected_values])

    if len(values) < expected_values:
        raise ValueError(f"PPM data is shorter than expected: {path}")

    scale = 255 / max_value
    scaled = [max(0, min(255, round(value * scale))) for value in values[:expected_values]]
    pixels = tuple(
        (scaled[index], scaled[index + 1], scaled[index + 2])
        for index in range(0, expected_values, 3)
    )
    return LoadedImage(width=width, height=height, pixels=pixels)


def _ppm_tokens(data: bytes) -> Iterable[bytes]:
    index = 0
    length = len(data)
    while index < length:
        byte = data[index]
        if byte == 35:  # # comment
            while index < length and data[index] not in b"\r\n":
                index += 1
        elif byte in b" \t\r\n":
            index += 1
        else:
            start = index
            while index < length and data[index] not in b" \t\r\n#":
                index += 1
            yield data[start:index]


def _ppm_header_length(data: bytes, token_count: int) -> int:
    found = 0
    index = 0
    length = len(data)
    while index < length and found < token_count:
        if data[index] == 35:
            while index < length and data[index] not in b"\r\n":
                index += 1
        elif data[index] in b" \t\r\n":
            index += 1
        else:
            found += 1
            while index < length and data[index] not in b" \t\r\n#":
                index += 1
    while index < length and data[index] in b" \t\r\n":
        index += 1
    return index
