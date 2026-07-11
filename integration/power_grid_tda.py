"""
Enhanced TDA Explorer for power grids with electrical distance metrics.

Features:
  - Multiple distance metric selection (PTDF, Effective R, LODF, etc.)
  - VR complex growth visualization
  - Persistence diagram
  - Betti curves (β₀, β₁)
  - Side-by-side comparison of different metrics
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from electrical_distance.ptdf_calculator import (
    compute_ptdf,
    compute_lodf,
    compute_effective_resistance_matrix,
    compute_ptdf_vector_distance,
    compute_bus_lodf_sensitivity,
)
from tda.vr_core import VRComplex
from tda.vulnerability import compute_vulnerability_scores, rank_vulnerable_buses, compute_vulnerability_summary


# ─── Distance metric registry ────────────────────────────────

METRICS = {
    "PTDF Vector (L2)": {
        "desc": "||PTDF[:,i] - PTDF[:,j]||₂ — buses with similar injection impact are close",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_ptdf_vector(data, p=2),
    },
    "PTDF Vector (L1)": {
        "desc": "||PTDF[:,i] - PTDF[:,j]||₁ — Manhattan variant",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_ptdf_vector(data, p=1),
    },
    "Effective Resistance": {
        "desc": "(eᵢ-eⱼ)ᵀL⁺(eᵢ-eⱼ) — true electrical distance metric",
        "needs": ["bus_pairs", "susceptances", "n_bus"],
        "fn": lambda data: _metric_effective_resistance(data),
    },
    "Bus LODF Sensitivity": {
        "desc": "||LODF_sens_i - LODF_sens_j||₂ — similarity in outage response",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_bus_lodf(data),
    },
    "PTDF Inverse": {
        "desc": "1/(1 + ||PTDF_i - PTDF_j||₂) — normalized to [0,1]",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_ptdf_inverse(data),
    },
    "Geographic (Euclidean)": {
        "desc": "Actual pixel/geographic distance between nodes",
        "needs": ["positions"],
        "fn": lambda data: _metric_geographic(data),
    },
}


def _metric_ptdf_vector(data: dict, p: float = 2) -> np.ndarray:
    PTDF = compute_ptdf(data["n_bus"], data["bus_pairs"], data["susceptances"])
    return compute_ptdf_vector_distance(PTDF, p_norm=p)


def _metric_effective_resistance(data: dict) -> np.ndarray:
    return compute_effective_resistance_matrix(data["n_bus"], data["bus_pairs"], data["susceptances"])


def _metric_bus_lodf(data: dict) -> np.ndarray:
    PTDF = compute_ptdf(data["n_bus"], data["bus_pairs"], data["susceptances"])
    LODF = compute_lodf(PTDF, data["bus_pairs"])
    return compute_bus_lodf_sensitivity(PTDF, LODF, data["bus_pairs"])


def _metric_ptdf_inverse(data: dict) -> np.ndarray:
    PTDF = compute_ptdf(data["n_bus"], data["bus_pairs"], data["susceptances"])
    D = compute_ptdf_vector_distance(PTDF, p_norm=2)
    return 1.0 / (1.0 + D)


def _metric_geographic(data: dict) -> np.ndarray:
    positions = data["positions"]
    n = len(positions)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            d = np.sqrt(dx * dx + dy * dy)
            D[i, j] = d
            D[j, i] = d
    return D


# ─── Enhanced TDA Explorer Window ────────────────────────────


class PowerGridTDAExplorer:
    """
    TDA analysis window for power grids with electrical distance metrics.

    Opens a new tkinter window with:
      - Distance metric selector (dropdown)
      - VR complex growth visualization
      - Persistence diagram
      - Betti curves (matplotlib or canvas-based)
      - Metric comparison mode
    """

    CANVAS_W = 500
    CANVAS_H = 500

    def __init__(self, parent: tk.Tk, electrical_data: dict):
        """
        Parameters
        ----------
        parent : tk.Tk
            Parent window.
        electrical_data : dict
            From GridGraphConverter.get_electrical_data().
            Must contain: n_bus, n_line, bus_pairs, susceptances.
            Optional: bus_positions, bus_labels.
        """
        self.parent = parent
        self.data = electrical_data
        self.win: tk.Toplevel | None = None

    def open(self):
        """Open the TDA explorer window."""
        self.win = tk.Toplevel(self.parent)
        self.win.title("Power Grid TDA Explorer")
        self.win.geometry("1200x800")
        self.win.configure(bg="#1E1E2E")

        # Top controls
        top = ttk.Frame(self.win, padding=5)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Distance Metric:").pack(side=tk.LEFT)
        metric_var = tk.StringVar(value=list(METRICS.keys())[0])
        metric_menu = ttk.Combobox(
            top, textvariable=metric_var,
            values=list(METRICS.keys()), state="readonly", width=25,
        )
        metric_menu.pack(side=tk.LEFT, padx=5)

        desc_label = ttk.Label(top, text="", foreground="#888888")
        desc_label.pack(side=tk.LEFT, padx=10)

        # Metric info
        ttk.Label(top, text="  β₀:").pack(side=tk.RIGHT)
        b0_lbl = ttk.Label(top, text="", width=4)
        b0_lbl.pack(side=tk.RIGHT)
        ttk.Label(top, text="β₁:").pack(side=tk.RIGHT)
        b1_lbl = ttk.Label(top, text="", width=4)
        b1_lbl.pack(side=tk.RIGHT)

        # Main split: left VR view, right persistence + betti
        main = ttk.Frame(self.win)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: VR view
        vr_frame = ttk.LabelFrame(main, text="Vietoris-Rips Complex")
        vr_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        vr_canvas = tk.Canvas(
            vr_frame, width=self.CANVAS_W, height=self.CANVAS_H,
            bg="#1E1E2E", highlightthickness=0,
        )
        vr_canvas.pack(fill=tk.BOTH, expand=True)

        # Right: persistence diagram + Betti curves
        right_frame = ttk.Frame(main)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        pd_frame = ttk.LabelFrame(right_frame, text="Persistence Diagram")
        pd_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        pd_canvas = tk.Canvas(
            pd_frame, width=400, height=300,
            bg="#1E1E2E", highlightthickness=0,
        )
        pd_canvas.pack(fill=tk.BOTH, expand=True)

        bc_frame = ttk.LabelFrame(right_frame, text="Betti Curves")
        bc_frame.pack(fill=tk.BOTH, expand=True)
        bc_canvas = tk.Canvas(
            bc_frame, width=400, height=200,
            bg="#1E1E2E", highlightthickness=0,
        )
        bc_canvas.pack(fill=tk.BOTH, expand=True)

        # Slider for threshold
        slider_frame = ttk.Frame(self.win)
        slider_frame.pack(fill=tk.X, padx=10, pady=5)
        alpha_var = tk.DoubleVar(value=0)
        alpha_scale = ttk.Scale(
            slider_frame, from_=0, to=100, variable=alpha_var,
            orient=tk.HORIZONTAL, length=300,
        )
        alpha_scale.pack(side=tk.LEFT, padx=10)
        alpha_label = ttk.Label(slider_frame, text="α = 0.00", width=12)
        alpha_label.pack(side=tk.LEFT)

        # Animate + Compare + Vulnerability buttons
        ttk.Button(slider_frame, text="▶ Animate",
                   command=lambda: self._animate(vr_canvas, pd_canvas, bc_canvas,
                                                  metric_var, alpha_var, alpha_scale,
                                                  b0_lbl, b1_lbl, desc_label)).pack(side=tk.RIGHT, padx=5)
        ttk.Button(slider_frame, text="📊 Compare All Metrics",
                   command=lambda: self._compare_metrics()).pack(side=tk.RIGHT, padx=5)
        ttk.Button(slider_frame, text="⚠ 취약점 분석",
                   command=self._vulnerability_analysis).pack(side=tk.RIGHT, padx=5)

        # State
        self._metric_var = metric_var
        self._alpha_var = alpha_var
        self._alpha_label = alpha_label
        self._b0_lbl = b0_lbl
        self._b1_lbl = b1_lbl
        self._desc_label = desc_label
        self._vr_canvas = vr_canvas
        self._pd_canvas = pd_canvas
        self._bc_canvas = bc_canvas
        self._alpha_scale = alpha_scale
        self._current_vr: VRComplex | None = None
        self._current_D: np.ndarray | None = None
        self._node_positions: list[tuple[float, float]] = []

        # Update description on metric change
        def on_metric_change(*_):
            name = metric_var.get()
            if name in METRICS:
                desc_label.config(text=METRICS[name]["desc"][:60])
            self._update_vr(
                vr_canvas, pd_canvas, bc_canvas,
                alpha_var, b0_lbl, b1_lbl,
            )

        metric_var.trace_add("write", on_metric_change)

        # Slider callback
        def on_slider(*_):
            self._update_vr(
                vr_canvas, pd_canvas, bc_canvas,
                alpha_var, b0_lbl, b1_lbl,
            )

        alpha_var.trace_add("write", on_slider)

        # Initial draw
        on_metric_change()

    def _get_distance_matrix(self, metric_name: str) -> np.ndarray:
        """Compute distance matrix for the given metric name."""
        if metric_name not in METRICS:
            raise ValueError(f"Unknown metric: {metric_name}")

        data = dict(self.data)
        # Add positions from the graph canvas if available (for geographic)
        if hasattr(self.parent, "app") and hasattr(self.parent.app, "nodes"):
            data["positions"] = [(n.x, n.y) for n in self.parent.app.nodes]
        else:
            data["positions"] = self.data.get("bus_positions", [(0, 0)] * self.data["n_bus"])

        return METRICS[metric_name]["fn"](data)

    def _update_vr(self, vr_canvas, pd_canvas, bc_canvas,
                   alpha_var, b0_lbl, b1_lbl):
        """Recompute and redraw with current metric + alpha."""
        name = self._metric_var.get()
        D = self._get_distance_matrix(name)
        self._current_D = D

        vr = VRComplex(D)
        self._current_vr = vr
        h0, h1 = vr.persistence_pairs()

        # Get node positions
        if hasattr(self.parent, "app") and hasattr(self.parent.app, "nodes"):
            self._node_positions = [(n.x, n.y) for n in self.parent.app.nodes]
        else:
            self._node_positions = self.data.get("bus_positions", [(0, 0)] * D.shape[0])

        # Scale slider to actual distance range
        max_d = vr.max_distance
        self._alpha_scale.config(to=max_d if max_d > 0 else 1)

        alpha = alpha_var.get()
        self._alpha_label.config(text=f"α = {alpha:.3f}")

        # Draw VR view
        self._draw_vr_view(vr_canvas, D, vr, alpha)

        # Draw persistence diagram
        self._draw_persistence_diagram(pd_canvas, h0, h1, max_d, alpha)

        # Draw Betti curves
        self._draw_betti_curves(bc_canvas, vr)

        # Update Betti labels
        b0, b1 = vr.betti_numbers(float(alpha))
        b0_lbl.config(text=str(b0))
        b1_lbl.config(text=str(b1))

    def _draw_vr_view(self, canvas, D, vr, alpha):
        """Draw nodes and VR edges at threshold alpha."""
        canvas.delete("all")
        cw = self.CANVAS_W
        ch = self.CANVAS_H

        # Scale positions to canvas
        positions = self._node_positions
        if not positions:
            return
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        rx = max(max_x - min_x, 1)
        ry = max(max_y - min_y, 1)
        margin = 40
        scaled = []
        for x, y in positions:
            sx = margin + ((x - min_x) / rx) * (cw - 2 * margin)
            sy = margin + ((y - min_y) / ry) * (ch - 2 * margin)
            scaled.append((sx, sy))

        # Draw edges at this threshold
        n = D.shape[0]
        for i in range(n):
            for j in range(i + 1, n):
                if D[i, j] <= alpha + 1e-10:
                    x1, y1 = scaled[i]
                    x2, y2 = scaled[j]
                    canvas.create_line(x1, y1, x2, y2, fill="#FFD700",
                                       width=2, tags="vr_edge")

        # Draw nodes
        r = 14
        for i, (sx, sy) in enumerate(scaled):
            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill="#4A90D9", outline="white", width=2)
            canvas.create_text(sx, sy, text=str(i),
                               fill="white", font=("Helvetica", 9, "bold"))

    def _draw_persistence_diagram(self, canvas, h0, h1, max_d, alpha, w=400, h=300):
        """Draw persistence diagram on canvas."""
        canvas.delete("all")
        margin = 30
        pw = w - 2 * margin
        ph = h - 2 * margin
        pm = max_d * 1.5 if max_d > 0 else 1.0

        # Axes
        canvas.create_line(margin, h - margin, w - margin, h - margin, fill="#555")
        canvas.create_line(margin, margin, margin, h - margin, fill="#555")
        # Diagonal
        canvas.create_line(margin, h - margin, margin + pw, margin, fill="#444", dash=(4, 4))

        if pm <= 0:
            return

        def tc(b, d):
            x = margin + (b / pm) * pw
            y = margin + ph - (d / pm) * ph
            return x, y

        # H0 points (blue) — skip birth=death (diagonal) points
        for b, d in h0:
            if b >= d - 1e-12:
                continue
            cx, cy = tc(b, d)
            canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                               fill="#4A90D9", outline="#4A90D9")

        # H1 points (red) — skip birth=death (diagonal) points
        for b, d in h1:
            if b >= d - 1e-12:
                continue
            cx, cy = tc(b, d)
            canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                               fill="#FF6B6B", outline="#FF6B6B")

        # Alpha marker
        ax = margin + (alpha / pm) * pw
        ay = margin + ph - (alpha / pm) * ph
        canvas.create_oval(ax - 5, ay - 5, ax + 5, ay + 5,
                           fill="white", outline="white", tags="marker")

        # Legend
        canvas.create_oval(margin + 10, margin + 5, margin + 16, margin + 11,
                           fill="#4A90D9", outline="")
        canvas.create_text(margin + 22, margin + 8, text="H₀", fill="#AAA",
                           font=("Helvetica", 9), anchor=tk.W)
        canvas.create_oval(margin + 10, margin + 20, margin + 16, margin + 26,
                           fill="#FF6B6B", outline="")
        canvas.create_text(margin + 22, margin + 23, text="H₁", fill="#AAA",
                           font=("Helvetica", 9), anchor=tk.W)

    def _draw_betti_curves(self, canvas, vr, w=400, h=200):
        """Draw Betti curves using canvas (no matplotlib needed)."""
        canvas.delete("all")
        thr, b0v, b1v = vr.betti_curves()
        if len(thr) < 2:
            canvas.create_text(w // 2, h // 2, text="Need more data",
                               fill="#888", font=("Helvetica", 11))
            return

        margin = 35
        pw = w - 2 * margin
        ph = h - 2 * margin

        # Axes
        canvas.create_line(margin, h - margin, w - margin, h - margin, fill="#555")
        canvas.create_line(margin, margin, margin, h - margin, fill="#555")

        # Plot
        max_b = max(max(b0v), max(b1v), 1)
        t_min, t_max = float(thr[0]), float(thr[-1])
        t_rng = max(t_max - t_min, 0.01)

        def to_canvas(t, b):
            x = margin + ((t - t_min) / t_rng) * pw
            y = margin + ph - (b / max_b) * ph
            return x, y

        # Draw β₁ curve
        pts_b1 = []
        for i in range(len(thr)):
            x, y = to_canvas(float(thr[i]), int(b1v[i]))
            pts_b1.append((x, y))
        if len(pts_b1) > 1:
            for i in range(len(pts_b1) - 1):
                canvas.create_line(pts_b1[i][0], pts_b1[i][1],
                                   pts_b1[i + 1][0], pts_b1[i + 1][1],
                                   fill="#FF6B6B", width=2)

        # Draw β₀ curve
        pts_b0 = []
        for i in range(len(thr)):
            x, y = to_canvas(float(thr[i]), int(b0v[i]))
            pts_b0.append((x, y))
        if len(pts_b0) > 1:
            for i in range(len(pts_b0) - 1):
                canvas.create_line(pts_b0[i][0], pts_b0[i][1],
                                   pts_b0[i + 1][0], pts_b0[i + 1][1],
                                   fill="#4A90D9", width=2)

        # Labels
        canvas.create_text(w // 2, h - 3, text="Threshold α", fill="#AAA",
                           font=("Helvetica", 8))
        canvas.create_text(12, h // 2, text="β", fill="#AAA",
                           font=("Helvetica", 8))
        # Legend
        canvas.create_line(margin + 10, margin + 5, margin + 25, margin + 5,
                           fill="#4A90D9", width=2)
        canvas.create_text(margin + 30, margin + 5, text="β₀", fill="#AAA",
                           font=("Helvetica", 9), anchor=tk.W)
        canvas.create_line(margin + 10, margin + 18, margin + 25, margin + 18,
                           fill="#FF6B6B", width=2)
        canvas.create_text(margin + 30, margin + 18, text="β₁", fill="#AAA",
                           font=("Helvetica", 9), anchor=tk.W)

    def _animate(self, vr_canvas, pd_canvas, bc_canvas,
                 metric_var, alpha_var, alpha_scale, b0_lbl, b1_lbl, desc_label):
        """Animate the VR complex growing step by step."""
        if self._current_vr is None:
            return

        steps = self._current_vr.unique_thresholds
        if len(steps) < 2:
            return

        def step_forward(idx):
            if idx < len(steps):
                alpha_var.set(float(steps[idx]))
                self.win.after(100, step_forward, idx + 1)

        self.win.after(100, step_forward, 0)

    def _compare_metrics(self):
        """Open a comparison window showing all metrics side by side."""
        win = tk.Toplevel(self.win)
        win.title("Metric Comparison")
        win.geometry("900x600")
        win.configure(bg="#1E1E2E")

        # Use matplotlib if available (it is), else canvas-based
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig, axes = plt.subplots(2, 3, figsize=(10, 6))
            fig.patch.set_facecolor("#1E1E2E")
            axes = axes.flatten()

            for ax, (name, info) in zip(axes, list(METRICS.items())):
                D = self._get_distance_matrix(name)
                vr = VRComplex(D)
                h0, h1 = vr.persistence_pairs()

                ax.clear()
                ax.set_facecolor("#2A2A3E")
                ax.set_title(name, color="white", fontsize=9)

                # Scatter persistence diagram — skip birth=death (diagonal) points
                births_h0 = [b for b, d in h0 if d < 1e10 and b < d - 1e-12]
                deaths_h0 = [d for b, d in h0 if d < 1e10 and b < d - 1e-12]
                births_h1 = [b for b, d in h1 if d < 1e10 and b < d - 1e-12]
                deaths_h1 = [d for b, d in h1 if d < 1e10 and b < d - 1e-12]

                ax.scatter(births_h0, deaths_h0, c="#4A90D9", s=8, alpha=0.7, label="H₀")
                ax.scatter(births_h1, deaths_h1, c="#FF6B6B", s=8, alpha=0.7, label="H₁")
                ax.plot([0, max(births_h0 + births_h1 + [1]) * 1.2] if births_h0 + births_h1 else [0, 1],
                        [0, max(births_h0 + births_h1 + [1]) * 1.2] if births_h0 + births_h1 else [0, 1],
                        "--", color="#555", linewidth=0.5)
                ax.tick_params(colors="#888", labelsize=7)
                ax.legend(fontsize=7, loc="lower right")

            plt.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except ImportError:
            # Fallback: text-based comparison
            txt = tk.Text(win, bg="#1E1E2E", fg="#FFF", font=("Courier", 10))
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            txt.insert(tk.END, f"{'Metric':<30} {'H₀ pairs':<12} {'H₁ pairs':<12} {'Max dist':<12}\n")
            txt.insert(tk.END, "-" * 66 + "\n")
            for name in METRICS:
                D = self._get_distance_matrix(name)
                vr = VRComplex(D)
                h0, h1 = vr.persistence_pairs()
                txt.insert(tk.END,
                    f"{name:<30} {len(h0):<12} {len([p for p in h1 if p[1] < 1e10]):<12} "
                    f"{vr.max_distance:<12.4f}\n"
                )

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)

    def _vulnerability_analysis(self):
        """Run vulnerability analysis on the current metric and show results."""
        if self._current_D is None or self._current_vr is None:
            messagebox.showwarning("No Data", "Compute VR first by selecting a metric.")
            return

        metric_name = self._metric_var.get()
        D = self._current_D
        vr = self._current_vr

        # Get bus labels
        bus_labels = self.data.get("bus_labels", None)
        if bus_labels is None:
            bus_labels = [f"B{i}" for i in range(D.shape[0])]

        # Compute vulnerability summary
        summary = compute_vulnerability_summary(D, vr, bus_labels=bus_labels, top_k=5)

        # Show results window
        self._show_vulnerability_window(summary, metric_name)

        # Color VR nodes by vulnerability
        self._color_vr_nodes_by_vulnerability(self._vr_canvas, summary["scores"])

    def _show_vulnerability_window(self, summary: dict, metric_name: str):
        """Display vulnerability analysis results in a new window."""
        win = tk.Toplevel(self.win)
        win.title(f"Vulnerability Analysis — {metric_name}")
        win.geometry("700x600")
        win.configure(bg="#1E1E2E")

        # Title
        title = ttk.Label(win, text="⚠ Bus Vulnerability Ranking",
                          font=("Helvetica", 14, "bold"),
                          foreground="#FF6B6B", background="#1E1E2E")
        title.pack(pady=(10, 5))

        # Summary info
        info_frame = ttk.Frame(win)
        info_frame.pack(fill=tk.X, padx=20, pady=5)

        summary_text = (
            f"Total Buses: {summary['n_buses']}  |  "
            f"β₀ = {summary['overall_beta0']}  |  "
            f"β₁ = {summary['overall_beta1']}  |  "
            f"High Risk (>0.7): {summary['n_vulnerable_high']}  |  "
            f"Medium Risk (0.4-0.7): {summary['n_vulnerable_medium']}"
        )
        ttk.Label(info_frame, text=summary_text,
                  foreground="#CCCCCC", background="#1E1E2E").pack()

        # Ranking table
        table_frame = ttk.LabelFrame(win, text="Vulnerability Ranking (Top 5)")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Treeview for ranking
        columns = ("rank", "bus", "score", "level")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                            height=8, selectmode="browse")
        tree.heading("rank", text="Rank")
        tree.heading("bus", text="Bus")
        tree.heading("score", text="Score")
        tree.heading("level", text="Risk Level")
        tree.column("rank", width=60, anchor=tk.CENTER)
        tree.column("bus", width=100, anchor=tk.CENTER)
        tree.column("score", width=120, anchor=tk.CENTER)
        tree.column("level", width=150, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Style for treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2A2A3E", foreground="white",
                        fieldbackground="#2A2A3E", font=("Helvetica", 10))
        style.configure("Treeview.Heading", background="#3A3A5E", foreground="white",
                        font=("Helvetica", 10, "bold"))

        # Populate rows
        for rank, (idx, score, label) in enumerate(summary["ranked"], 1):
            if score > 0.7:
                level = "🔴 High Risk"
                tag = "high"
            elif score > 0.4:
                level = "🟡 Medium Risk"
                tag = "medium"
            else:
                level = "🟢 Low Risk"
                tag = "low"

            tree.insert("", tk.END, values=(rank, label, f"{score:.4f}", level),
                        tags=(tag,))

        tree.tag_configure("high", foreground="#FF6B6B")
        tree.tag_configure("medium", foreground="#FFD700")
        tree.tag_configure("low", foreground="#4A90D9")

        # Interpretation section
        interp_frame = ttk.LabelFrame(win, text="Interpretation")
        interp_frame.pack(fill=tk.X, padx=20, pady=10)

        n_high = summary["n_vulnerable_high"]
        n_medium = summary["n_vulnerable_medium"]
        b1 = summary["overall_beta1"]

        interp_lines = []
        if n_high > 0:
            interp_lines.append(
                f"• {n_high} bus(es) show HIGH vulnerability — these buses are electrically "
                "isolated or act as critical bridges in the distance space."
            )
        if n_medium > 0:
            interp_lines.append(
                f"• {n_medium} bus(es) show MEDIUM vulnerability — monitor these for potential issues."
            )
        if b1 == 0:
            interp_lines.append(
                "• No H₁ cycles detected — the grid has a tree-like topology with no redundant paths."
            )
        else:
            interp_lines.append(
                f"• {b1} H₁ cycle(s) detected — these provide redundancy and reduce vulnerability."
            )

        interp_text = "\n".join(interp_lines) if interp_lines else "• No significant vulnerabilities detected."
        ttk.Label(interp_frame, text=interp_text,
                  foreground="#CCCCCC", background="#1E1E2E",
                  wraplength=600, justify=tk.LEFT).pack(padx=10, pady=10)

        # Close button
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    def _color_vr_nodes_by_vulnerability(self, canvas, scores):
        """Recolor VR view nodes based on vulnerability scores (Red→Yellow→Green)."""
        # Find all node ovals and text items in the canvas
        # We need to delete and redraw the nodes with new colors
        # The nodes are drawn in _draw_vr_view, so we'll modify them there

        # For now, just update the colors on the existing canvas
        # Nodes are drawn as ovals; we need to find them by tag or position
        # Since we don't have tags, we'll use the stored node positions

        if not self._node_positions or len(self._node_positions) != len(scores):
            return

        cw = self.CANVAS_W
        ch = self.CANVAS_H
        positions = self._node_positions
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        rx = max(max_x - min_x, 1)
        ry = max(max_y - min_y, 1)
        margin = 40
        scaled = []
        for x, y in positions:
            sx = margin + ((x - min_x) / rx) * (cw - 2 * margin)
            sy = margin + ((y - min_y) / ry) * (ch - 2 * margin)
            scaled.append((sx, sy))

        r = 14
        for i, (sx, sy) in enumerate(scaled):
            # Color: Red (high vuln) → Yellow (medium) → Green (low)
            s = float(scores[i])
            if s > 0.7:
                color = "#FF4444"  # Red — high
            elif s > 0.4:
                color = "#FFAA00"  # Yellow — medium
            else:
                color = "#44BB44"  # Green — low

            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill=color, outline="white", width=2,
                               tags=("vuln_node",))
            canvas.create_text(sx, sy, text=str(i),
                               fill="white", font=("Helvetica", 9, "bold"),
                               tags=("vuln_label",))

