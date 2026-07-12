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
    build_incidence_matrix,
)
from tda.vr_core import VRComplex
from tda.vulnerability import compare_with_homology


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
    "LODF Inverse": {
        "desc": "||C[:,i]ᵀ·LODF⁺ - C[:,j]ᵀ·LODF⁺||₂ — LODF pseudo-inverse distance",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_lodf_inverse(data),
    },
    "KCL Current": {
        "desc": "||I_i - I_j||₂ — distance based on DC current injection profiles",
        "needs": ["bus_pairs", "susceptances"],
        "fn": lambda data: _metric_kcl_current(data),
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


def _metric_lodf_inverse(data: dict) -> np.ndarray:
    """LODF pseudo-inverse distance: ||C[:,i]ᵀ·LODF⁺ - C[:,j]ᵀ·LODF⁺||₂"""
    PTDF = compute_ptdf(data["n_bus"], data["bus_pairs"], data["susceptances"])
    LODF = compute_lodf(PTDF, data["bus_pairs"])
    LODF_pinv = np.linalg.pinv(LODF)
    C = build_incidence_matrix(data["n_bus"], data["bus_pairs"])

    n_bus = data["n_bus"]
    n_line = len(data["bus_pairs"])
    profiles = np.zeros((n_bus, n_line), dtype=np.float64)
    for i in range(n_bus):
        profiles[i, :] = C[:, i] @ LODF_pinv

    D = np.zeros((n_bus, n_bus), dtype=np.float64)
    for i in range(n_bus):
        for j in range(i + 1, n_bus):
            dist = np.linalg.norm(profiles[i] - profiles[j], ord=2)
            D[i, j] = dist
            D[j, i] = dist
    return D


def _metric_kcl_current(data: dict) -> np.ndarray:
    """KCL Current distance: ||I_i - I_j||₂ based on DC current injection profiles.

    For each bus i, computes the current injection vector I_i using the
    DC power flow approximation: I = B⁻¹ · P_inj where P_inj is a unit
    injection at bus i (with slack bus as reference).
    """
    from electrical_distance.metrics import KCLCurrentDistance
    metric = KCLCurrentDistance(p_norm=2)
    return metric.compute(data["n_bus"], data["bus_pairs"], data["susceptances"])


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
            """Run N-1 contingency-based vulnerability analysis and homology comparison."""
            if self._current_D is None:
                messagebox.showwarning("No Data", "Compute VR first by selecting a metric.")
                return
    
            metric_name = self._metric_var.get()
            D = self._current_D
    
            # Get grid_data from electrical data (added by GridGraphConverter)
            grid_data = self.data.get("grid_data", None)
            if grid_data is None:
                messagebox.showerror("Error",
                    "No grid data available. Please import a power grid first.")
                return
    
            # Run N-1 contingency + homology comparison
            try:
                result = compare_with_homology(grid_data, D)
            except Exception as e:
                messagebox.showerror("Analysis Error",
                    f"Vulnerability analysis failed:\n{e}")
                return
    
            # Show results window
            self._show_vulnerability_window(result, metric_name)
    
            # Color VR nodes by vulnerability + cycle membership
            self._color_vr_nodes_by_vulnerability(
                self._vr_canvas, grid_data, result)

    def _show_vulnerability_window(self, result: dict, metric_name: str):
        """Display N-1 contingency + homology comparison results."""
        win = tk.Toplevel(self.win)
        win.title(f"Vulnerability Analysis — {metric_name}")
        win.geometry("800x700")
        win.configure(bg="#1E1E2E")

        # Title
        title = ttk.Label(win, text="N-1 Contingency + Homology Comparison",
                          font=("Helvetica", 14, "bold"),
                          foreground="#FF6B6B", background="#1E1E2E")
        title.pack(pady=(10, 5))

        # Summary bar
        info_frame = ttk.Frame(win)
        info_frame.pack(fill=tk.X, padx=20, pady=5)

        n1 = result["n1_analysis_summary"]
        summary_text = (
            f"Buses: {result['n_bus']}  |  "
            f"Lines: {result['n_line']}  |  "
            f"N-1 Vulnerable: {result['n_vulnerable']}/{result['n_line']} "
            f"({result['n1_analysis']['vulnerability_ratio']*100:.1f}%)  |  "
            f"H1 Cycle Edges: {result['n_cycle_edges']}"
        )
        ttk.Label(info_frame, text=summary_text,
                  foreground="#CCCCCC", background="#1E1E2E").pack()

        # Alignment Score
        alignment_frame = ttk.LabelFrame(win, text="Alignment: Homology vs N-1 AC Analysis")
        alignment_frame.pack(fill=tk.X, padx=20, pady=5)

        align = result["alignment_score"]
        prec = result["precision"]
        rec = result["recall"]
        spec = result["specificity"]

        align_text = (
            f"Alignment Score: {align:.4f}  "
            f"(Intersection / Total Edges = {len(result['intersection'])} / {result['n_line']})\n"
            f"Precision: {prec:.4f}  |  "
            f"Recall: {rec:.4f}  |  "
            f"Specificity: {spec:.4f}"
        )
        ttk.Label(alignment_frame, text=align_text,
                  foreground="#FFD700", background="#1E1E2E",
                  font=("Helvetica", 11)).pack(padx=10, pady=8)

        # Vulnerable Edges (N-1) Table
        vuln_frame = ttk.LabelFrame(win, text="N-1 Vulnerable Edges (AC Power Flow)")
        vuln_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        vuln_columns = ("id", "name", "violations")
        vuln_tree = ttk.Treeview(vuln_frame, columns=vuln_columns, show="headings",
                                 height=6, selectmode="browse")
        vuln_tree.heading("id", text="Line ID")
        vuln_tree.heading("name", text="Name")
        vuln_tree.heading("violations", text="Violations")
        vuln_tree.column("id", width=60, anchor=tk.CENTER)
        vuln_tree.column("name", width=120, anchor=tk.W)
        vuln_tree.column("violations", width=200, anchor=tk.W)

        vuln_scroll = ttk.Scrollbar(vuln_frame, orient=tk.VERTICAL, command=vuln_tree.yview)
        vuln_tree.configure(yscrollcommand=vuln_scroll.set)
        vuln_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        vuln_tree.pack(fill=tk.BOTH, expand=True)

        for edge in n1.get("vulnerable_edges_detail", []):
            violations_str = ", ".join(edge["violations"])
            vuln_tree.insert("", tk.END,
                             values=(edge["id"], edge["name"], violations_str),
                             tags=("vuln",))

        vuln_tree.tag_configure("vuln", foreground="#FF6B6B")

        # Cycle Edges (Homology) Table
        cycle_frame = ttk.LabelFrame(win, text="H1 Cycle Edges (Homology Candidates)")
        cycle_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        cycle_columns = ("id", "name", "in_vulnerable")
        cycle_tree = ttk.Treeview(cycle_frame, columns=cycle_columns, show="headings",
                                  height=6, selectmode="browse")
        cycle_tree.heading("id", text="Line ID")
        cycle_tree.heading("name", text="Name")
        cycle_tree.heading("in_vulnerable", text="In N-1 Vulnerable?")
        cycle_tree.column("id", width=60, anchor=tk.CENTER)
        cycle_tree.column("name", width=120, anchor=tk.W)
        cycle_tree.column("in_vulnerable", width=140, anchor=tk.CENTER)

        cycle_scroll = ttk.Scrollbar(cycle_frame, orient=tk.VERTICAL, command=cycle_tree.yview)
        cycle_tree.configure(yscrollcommand=cycle_scroll.set)
        cycle_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        cycle_tree.pack(fill=tk.BOTH, expand=True)

        # Build name lookup for cycle edges
        line_names = {}
        for l in result["n1_analysis"]["violation_details"]:
            detail = result["n1_analysis"]["violation_details"][l]
            line_names[l] = detail["line_name"]

        for cid in sorted(result["cycle_edge_ids"]):
            is_vuln = cid in result["vulnerable_edge_ids"]
            in_vuln_str = "YES" if is_vuln else "No"
            tag = "match" if is_vuln else "nomatch"
            cycle_tree.insert("", tk.END,
                              values=(cid, line_names.get(cid, f"L{cid}"), in_vuln_str),
                              tags=(tag,))

        cycle_tree.tag_configure("match", foreground="#44BB44")
        cycle_tree.tag_configure("nomatch", foreground="#FFAA00")

        # Homology Info
        homo_info = result.get("homology", {})
        if homo_info:
            homo_frame = ttk.LabelFrame(win, text="Persistence Homology Info")
            homo_frame.pack(fill=tk.X, padx=20, pady=5)

            h0_n = homo_info["n_h0"]
            h1_n = homo_info["n_h1"]
            h1_persistent = homo_info["n_h1_persistent"]
            max_d = homo_info["max_distance"]

            homo_text = (
                f"H0 pairs: {h0_n}  |  "
                f"H1 pairs: {h1_n}  |  "
                f"Persistent H1: {h1_persistent}  |  "
                f"Max distance: {max_d:.4f}"
            )
            ttk.Label(homo_frame, text=homo_text,
                      foreground="#CCCCCC", background="#1E1E2E").pack(padx=10, pady=5)

        # Interpretation
        interp_frame = ttk.LabelFrame(win, text="Interpretation")
        interp_frame.pack(fill=tk.X, padx=20, pady=10)

        interp_lines = [
            f"* {result['n_vulnerable']} out of {result['n_line']} lines are N-1 vulnerable "
            f"(AC power flow analysis).",
        ]
        if result["n_cycle_edges"] > 0:
            interp_lines.append(
                f"* {result['n_cycle_edges']} line(s) belong to persistent H1 cycles "
                f"(homology candidates)."
            )
            interp_lines.append(
                f"* Alignment score = {align:.4f}: homology cycle edges match "
                f"N-1 vulnerable edges at {align*100:.1f}% of total edges."
            )
            if prec > 0.5:
                interp_lines.append(
                    f"* Precision = {prec:.4f}: {prec*100:.1f}% of cycle edges are "
                    f"actually N-1 vulnerable."
                )
        else:
            interp_lines.append(
                "* No H1 cycles detected - the grid has a tree-like topology "
                "with no redundant paths."
            )

        interp_text = "\n".join(interp_lines)
        ttk.Label(interp_frame, text=interp_text,
                  foreground="#CCCCCC", background="#1E1E2E",
                  wraplength=700, justify=tk.LEFT).pack(padx=10, pady=10)

        # Close button
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    def _color_vr_nodes_by_vulnerability(self, canvas, grid_data, result):
        """Recolor VR view nodes: red if incident to vulnerable edge, yellow if cycle member."""
        if not self._node_positions:
            return

        vulnerable_edge_ids = result["vulnerable_edge_ids"]
        cycle_edge_ids = result["cycle_edge_ids"]

        # Find buses incident to vulnerable / cycle edges
        vuln_buses = set()
        cycle_buses = set()
        for l in grid_data.get("lines", []):
            lid = l["id"]
            f, t = l["from_bus"], l["to_bus"]
            if lid in vulnerable_edge_ids:
                vuln_buses.add(f)
                vuln_buses.add(t)
            if lid in cycle_edge_ids:
                cycle_buses.add(f)
                cycle_buses.add(t)

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
            if i in vuln_buses:
                color = "#FF4444"  # Red - incident to N-1 vulnerable edge
            elif i in cycle_buses:
                color = "#FFAA00"  # Yellow - in H1 cycle
            else:
                color = "#44BB44"  # Green - neither

            canvas.create_oval(sx - r, sy - r, sx + r, sy + r,
                               fill=color, outline="white", width=2,
                               tags=("vuln_node",))
            canvas.create_text(sx, sy, text=str(i),
                               fill="white", font=("Helvetica", 9, "bold"),
                               tags=("vuln_label",))