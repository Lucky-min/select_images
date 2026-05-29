"""Utilities for selecting the best image from burst-shot photo groups."""

from .selector import ImageCandidate, SelectionResult, select_best_images

__all__ = ["ImageCandidate", "SelectionResult", "select_best_images"]
