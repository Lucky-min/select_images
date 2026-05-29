"""Command line interface for burst-photo best-shot selection."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .selector import SelectionResult, select_best_images


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select the best photo from each burst-shot group."
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing photos to evaluate")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Optional directory where selected winners will be copied",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Scan input directory recursively"
    )
    parser.add_argument(
        "-w",
        "--burst-window",
        type=float,
        default=2.0,
        help="Maximum seconds between neighboring photos in the same burst group",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional CSV report path with winners and rejected photos",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input_dir.exists() or not args.input_dir.is_dir():
        parser.error(f"input_dir must be an existing directory: {args.input_dir}")

    try:
        results = select_best_images(
            args.input_dir,
            recursive=args.recursive,
            burst_window_seconds=args.burst_window,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("No supported image files found.")
        return 0

    _print_results(results)
    if args.report:
        _write_report(args.report, results)
        print(f"CSV report written to: {args.report}")
    return 0


def _print_results(results: list[SelectionResult]) -> None:
    for index, result in enumerate(results, start=1):
        score = result.winner.score
        print(
            f"Group {index}: winner={result.winner.path} "
            f"score={score.total:.3f} sharpness={score.sharpness:.3f} "
            f"exposure={score.exposure:.3f} rejected={len(result.rejected)}"
        )
        for rejected in result.rejected:
            print(f"  reject={rejected.path} score={rejected.score.total:.3f}")


def _write_report(path: Path, results: list[SelectionResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as report_file:
        writer = csv.writer(report_file)
        writer.writerow(
            [
                "group",
                "selected",
                "path",
                "total",
                "sharpness",
                "exposure",
                "contrast",
                "saturation",
                "resolution",
            ]
        )
        for group_index, result in enumerate(results, start=1):
            for candidate in result.group:
                writer.writerow(
                    [
                        group_index,
                        candidate == result.winner,
                        candidate.path,
                        candidate.score.total,
                        candidate.score.sharpness,
                        candidate.score.exposure,
                        candidate.score.contrast,
                        candidate.score.saturation,
                        candidate.score.resolution,
                    ]
                )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
