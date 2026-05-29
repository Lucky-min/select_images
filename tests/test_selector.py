from __future__ import annotations

from pathlib import Path

from select_images.cli import main
from select_images.selector import select_best_images


def test_selects_sharper_image_from_burst(tmp_path: Path) -> None:
    blurry = tmp_path / "burst_001.ppm"
    sharp = tmp_path / "burst_002.ppm"
    _write_ppm(blurry, _flat_pixels())
    _write_ppm(sharp, _checker_pixels())

    blurry_time = 1_700_000_000
    sharp_time = blurry_time + 1
    blurry.touch()
    sharp.touch()
    _set_mtime(blurry, blurry_time)
    _set_mtime(sharp, sharp_time)

    results = select_best_images(tmp_path, burst_window_seconds=2)

    assert len(results) == 1
    assert results[0].winner.path == sharp
    assert results[0].rejected[0].path == blurry


def test_separates_photos_outside_burst_window(tmp_path: Path) -> None:
    first = tmp_path / "first.ppm"
    second = tmp_path / "second.ppm"
    _write_ppm(first, _checker_pixels())
    _write_ppm(second, _checker_pixels())
    _set_mtime(first, 1_700_000_000)
    _set_mtime(second, 1_700_000_010)

    results = select_best_images(tmp_path, burst_window_seconds=2)

    assert len(results) == 2
    assert [result.winner.path for result in results] == [first, second]


def test_cli_writes_report_and_copies_winner(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    report = tmp_path / "report.csv"
    source.mkdir()
    blurry = source / "burst_001.ppm"
    sharp = source / "burst_002.ppm"
    _write_ppm(blurry, _flat_pixels())
    _write_ppm(sharp, _checker_pixels())
    _set_mtime(blurry, 1_700_000_000)
    _set_mtime(sharp, 1_700_000_001)

    exit_code = main([str(source), "--output-dir", str(output), "--report", str(report)])

    assert exit_code == 0
    assert (output / sharp.name).exists()
    assert report.read_text(encoding="utf-8").startswith("group,selected,path,total")


def _write_ppm(path: Path, pixels: list[tuple[int, int, int]]) -> None:
    width = 8
    height = 8
    values = "\n".join(f"{red} {green} {blue}" for red, green, blue in pixels)
    path.write_text(f"P3\n{width} {height}\n255\n{values}\n", encoding="ascii")


def _flat_pixels() -> list[tuple[int, int, int]]:
    return [(128, 128, 128) for _ in range(64)]


def _checker_pixels() -> list[tuple[int, int, int]]:
    pixels: list[tuple[int, int, int]] = []
    for y in range(8):
        for x in range(8):
            pixels.append((230, 230, 230) if (x + y) % 2 == 0 else (30, 30, 30))
    return pixels


def _set_mtime(path: Path, timestamp: int) -> None:
    import os

    os.utime(path, (timestamp, timestamp))
