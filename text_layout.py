"""
Auto text layout helper: choose high-contrast placement and styling for overlays.

Responsibilities:
- Sample luminance across a 3x3 grid of frames to find the best placement.
- Pick text color (white/black) that maximizes contrast in the chosen cell.
- Suggest a sane font size based on video height with min/max bounds.
- Optionally generate the three text segments via ChatGPT when none are supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from moviepy import VideoFileClip

from chatgpt_integration import generate_three_text_segments, logger as gpt_logger

# Reuse canonical location names
LOCATION_NAMES = {
    "top-left": (0, 0),
    "top-center": (0, 1),
    "top-right": (0, 2),
    "center-left": (1, 0),
    "center-center": (1, 1),
    "center-right": (1, 2),
    "bottom-left": (2, 0),
    "bottom-center": (2, 1),
    "bottom-right": (2, 2),
}


@dataclass
class LayoutChoice:
    location: str
    text_color: str  # hex like "#FFFFFF"
    contrast_score: float
    mean_luminance: float
    font_size: int

    def to_json(self) -> Dict[str, object]:
        return {
            "location": self.location,
            "text_color": self.text_color,
            "contrast_score": self.contrast_score,
            "mean_luminance": self.mean_luminance,
            "font_size": self.font_size,
        }


def _sample_luminance_grid(
    clip: VideoFileClip, *, samples: int = 5, grid_size: Tuple[int, int] = (3, 3)
) -> np.ndarray:
    """
    Sample frames evenly across the clip and compute average luminance per grid cell.
    Returns a (rows x cols) array of luminance averages (0-255).
    """
    rows, cols = grid_size
    grid_accum = np.zeros((rows, cols), dtype=np.float64)
    total_frames = 0

    # Avoid first/last frame for stability
    time_points = np.linspace(0.05, 0.95, num=max(1, samples)) * clip.duration

    for t in time_points:
        frame = clip.get_frame(float(t))
        # Downscale for speed
        h, w = frame.shape[0], frame.shape[1]
        # reshape into grid
        tile_h = h // rows
        tile_w = w // cols
        if tile_h == 0 or tile_w == 0:
            continue

        # compute grayscale per tile
        for r in range(rows):
            for c in range(cols):
                y0, y1 = r * tile_h, (r + 1) * tile_h
                x0, x1 = c * tile_w, (c + 1) * tile_w
                tile = frame[y0:y1, x0:x1]
                # Luminance approximation
                lum = (
                    0.299 * tile[:, :, 0]
                    + 0.587 * tile[:, :, 1]
                    + 0.114 * tile[:, :, 2]
                )
                grid_accum[r, c] += float(lum.mean())
        total_frames += 1

    if total_frames == 0:
        return grid_accum
    return grid_accum / float(total_frames)


def _choose_best_cell(grid: np.ndarray) -> Tuple[str, float, float, str]:
    """
    Choose the cell and text color (white/black) that maximizes contrast.
    Returns (location, contrast_score, mean_luminance, text_color_hex).
    """
    best_location = "bottom"
    best_contrast = -1.0
    best_lum = 128.0
    best_color = "#FFFFFF"

    for loc, (r, c) in LOCATION_NAMES.items():
        lum = float(grid[r, c])
        contrast_white = 255.0 - lum
        contrast_black = lum

        if contrast_white >= contrast_black:
            contrast = contrast_white
            color = "#FFFFFF"
        else:
            contrast = contrast_black
            color = "#000000"

        if contrast > best_contrast:
            best_contrast = contrast
            best_location = loc
            best_lum = lum
            best_color = color

    return best_location, best_contrast, best_lum, best_color


def auto_layout_from_video(
    video_path: str,
    *,
    font_pct: float = 0.08334,
    min_font: int = 48,
    max_font: int = 140,
    grid_samples: int = 5,
) -> Optional[LayoutChoice]:
    """
    Analyze a video to select a single global placement and styling.
    """
    try:
        with VideoFileClip(video_path) as clip:
            grid = _sample_luminance_grid(clip, samples=grid_samples)
            location, contrast, lum, color = _choose_best_cell(grid)
            _, height = clip.size
            font_size = int(max(min_font, min(max_font, round(height * font_pct))))
            return LayoutChoice(
                location=location,
                text_color=color,
                contrast_score=contrast,
                mean_luminance=lum,
                font_size=font_size,
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        gpt_logger.error("[auto_layout_from_video] failed: %s", exc, exc_info=True)
        return None


def build_auto_overlay_package(
    *,
    category: str,
    subcategory: str = "",
    video_path: str,
    existing_texts: Optional[Sequence[str]] = None,
    additional_context: Optional[str] = None,
    default_location: str = "bottom",
) -> Optional[Dict[str, object]]:
    """
    Combine GPT text generation (if needed) with layout analysis for the given video.
    """
    texts: List[str] = []
    existing_texts = list(existing_texts) if existing_texts else []
    existing_texts = [t for t in existing_texts if isinstance(t, str) and t.strip()]

    if existing_texts:
        texts = list(existing_texts[:3])
        while len(texts) < 3:
            texts.append(existing_texts[-1])
    else:
        gpt_payload = generate_three_text_segments(
            category=category,
            subcategory=subcategory,
            additional_context=additional_context,
            default_location=default_location,
        )
        if not gpt_payload:
            return None
        texts = gpt_payload["texts"]

    layout = auto_layout_from_video(video_path)
    if not layout:
        return None

    return {
        "texts": texts[:3],
        "location": layout.location,
        "text_color": layout.text_color,
        "font_size": layout.font_size,
        "contrast_score": layout.contrast_score,
        "mean_luminance": layout.mean_luminance,
        "metadata": {
            "category": category,
            "subcategory": subcategory,
            "video_path": video_path,
        },
    }
