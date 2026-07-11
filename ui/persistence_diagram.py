"""Persistence diagram drawing helper for Tkinter canvases."""

from __future__ import annotations

import tkinter as tk
import numpy as np


def draw_persistence_diagram(
    canvas: tk.Canvas,
    h0_pairs: list[tuple[float, float]],
    h1_pairs: list[tuple[float, float]],
    max_dist: float,
    width: int = 450,
    height: int = 450,
):
    """Draw a persistence diagram on a tkinter Canvas.

    Parameters
    ----------
    canvas : tk.Canvas
        The canvas to draw on.
    h0_pairs : list of (birth, death)
        H₀ persistence pairs.
    h1_pairs : list of (birth, death)
        H₁ persistence pairs.
    max_dist : float
        Maximum distance in the distance matrix (for scaling).
    width, height : int
        Canvas dimensions.
    """
    margin = 30
    pd_w = width - 2 * margin
    pd_h = height - 2 * margin
    plot_max = max_dist * 1.6

    canvas.create_text(
        width // 2, height - 5,
        text="Birth (α)", fill="#AAAAAA", font=("Helvetica", 9),
    )
    canvas.create_text(
        15, height // 2,
        text="Death (α)", fill="#AAAAAA", font=("Helvetica", 9), angle=90,
    )

    canvas.create_line(
        margin, height - margin, width - margin, height - margin,
        fill="#555555",
    )
    canvas.create_line(margin, margin, margin, height - margin, fill="#555555")
    canvas.create_line(
        margin, height - margin, margin + pd_w, margin,
        fill="#444444", dash=(4, 4),
    )

    if plot_max <= 0:
        return

    def to_canvas(b: float, d: float) -> tuple[float, float]:
        x = margin + (b / plot_max) * pd_w
        y = margin + pd_h - (d / plot_max) * pd_h
        return x, y

    for b, d in h0_pairs:
        if b >= d - 1e-12:
            continue
        cx, cy = to_canvas(b, d)
        canvas.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill="#4A90D9", outline="#4A90D9", tags="pd_point",
        )

    for b, d in h1_pairs:
        if b >= d - 1e-12:
            continue
        cx, cy = to_canvas(b, d)
        canvas.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill="#FF6B6B", outline="#FF6B6B", tags="pd_point",
        )

    # Legend
    canvas.create_oval(
        margin + 10, margin + 5, margin + 16, margin + 11,
        fill="#4A90D9", outline="",
    )
    canvas.create_text(
        margin + 22, margin + 8, text="H₀",
        fill="#AAAAAA", font=("Helvetica", 9), anchor=tk.W,
    )
    canvas.create_oval(
        margin + 10, margin + 20, margin + 16, margin + 26,
        fill="#FF6B6B", outline="",
    )
    canvas.create_text(
        margin + 22, margin + 23, text="H₁",
        fill="#AAAAAA", font=("Helvetica", 9), anchor=tk.W,
    )

