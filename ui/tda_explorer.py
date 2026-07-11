"""TDA Explorer window — VR complex growth visualization with persistence diagram."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

import numpy as np

from tda.vr_core import VRComplex
from core.node import Node
from ui.persistence_diagram import draw_persistence_diagram


class TdaExplorerWindow:
    """Opens a TDA Explorer window with VR view, persistence diagram, and animation.

    Extracted from GraphEditor._tda_explorer() to reduce main file size.
    """

    VR_WIDTH = 500
    VR_HEIGHT = 500
    VR_MARGIN = 40
    PD_WIDTH = 450
    PD_HEIGHT = 450

    def __init__(self, root: tk.Tk, nodes: list, edges: list, on_ask_ai):
        self.root = root
        self.nodes = nodes
        self.edges = edges
        self.on_ask_ai = on_ask_ai

        self.win: tk.Toplevel | None = None
        self.vr: VRComplex | None = None

    def open(self):
        """Build and display the TDA Explorer window."""
        V = len(self.nodes)
        points = [(node.x, node.y) for node in self.nodes]

        # Build Euclidean distance matrix
        D = np.zeros((V, V))
        for i in range(V):
            for j in range(i + 1, V):
                dx = points[i][0] - points[j][0]
                dy = points[i][1] - points[j][1]
                d = math.sqrt(dx * dx + dy * dy)
                D[i, j] = D[j, i] = d

        # Compute VR Complex
        self.vr = VRComplex(D)
        h0_pairs, h1_pairs = self.vr.persistence_pairs()
        unique_dists = self.vr.unique_thresholds.tolist()
        max_dist = self.vr.max_distance

        # Sort dist pairs for VR edge drawing
        dist_pairs = []
        for i in range(V):
            for j in range(i + 1, V):
                dist_pairs.append((D[i, j], i, j))
        dist_pairs.sort()

        # Graph-level stats from user's own edges
        E = len(self.edges)
        gu_parent = list(range(V))

        def gu_find(x):
            while gu_parent[x] != x:
                gu_parent[x] = gu_parent[gu_parent[x]]
                x = gu_parent[x]
            return x

        def gu_union(x, y):
            px, py = gu_find(x), gu_find(y)
            if px != py:
                gu_parent[px] = py

        node_to_idx = {id(node): i for i, node in enumerate(self.nodes)}
        for edge in self.edges:
            u = node_to_idx.get(id(edge.source))
            v = node_to_idx.get(id(edge.target))
            if u is not None and v is not None:
                gu_union(u, v)
        comps_graph = set(gu_find(i) for i in range(V))
        beta0_graph = len(comps_graph)
        beta1_graph = E - V + beta0_graph
        euler_char = V - E

        # ── Build window ──────────────────────────────────────────
        self.win = tk.Toplevel(self.root)
        self.win.title("TDA 탐색기")
        self.win.geometry("1100x750")
        self.win.configure(bg="#1E1E2E")

        top_frame = ttk.Frame(self.win, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="α (거리 임계값):").pack(side=tk.LEFT)
        alpha_var = tk.DoubleVar(value=0)
        alpha_scale = ttk.Scale(
            top_frame, from_=0, to=unique_dists[-1],
            variable=alpha_var, orient=tk.HORIZONTAL, length=200,
        )
        alpha_scale.pack(side=tk.LEFT, padx=10)
        alpha_label = ttk.Label(top_frame, text="0.0", width=8)
        alpha_label.pack(side=tk.LEFT)

        ttk.Label(top_frame, text="  β₀:").pack(side=tk.LEFT)
        b0_label = ttk.Label(top_frame, text=str(V), width=3)
        b0_label.pack(side=tk.LEFT)
        ttk.Label(top_frame, text="  β₁:").pack(side=tk.LEFT)
        b1_label = ttk.Label(top_frame, text="0", width=3)
        b1_label.pack(side=tk.LEFT)

        ttk.Button(
            top_frame, text="🤖 AI 분석 (딥시크)",
            command=lambda: self.on_ask_ai(self.win),
        ).pack(side=tk.RIGHT, padx=5)

        stats_label = ttk.Label(
            top_frame,
            text=f"  |  V={V} E={E} χ={euler_char} β₀={beta0_graph} β₁={beta1_graph}",
        )
        stats_label.pack(side=tk.LEFT, padx=10)

        main_frame = ttk.Frame(self.win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ── VR View canvas ───────────────────────────────────────
        vr_frame = ttk.LabelFrame(main_frame, text="Vietoris-Rips Complex Growth")
        vr_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        vr_canvas = tk.Canvas(
            vr_frame, width=self.VR_WIDTH, height=self.VR_HEIGHT,
            bg="#1E1E2E", highlightthickness=0,
        )
        vr_canvas.pack(fill=tk.BOTH, expand=True)

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        rx = max(max_x - min_x, 1)
        ry = max(max_y - min_y, 1)

        scaled_positions = []
        for node in self.nodes:
            sx = self.VR_MARGIN + ((node.x - min_x) / rx) * (self.VR_WIDTH - 2 * self.VR_MARGIN)
            sy = self.VR_MARGIN + ((node.y - min_y) / ry) * (self.VR_HEIGHT - 2 * self.VR_MARGIN)
            scaled_positions.append((sx, sy))

        for sx, sy in scaled_positions:
            vr_canvas.create_oval(
                sx - 12, sy - 12, sx + 12, sy + 12,
                fill=Node.COLOR_NORMAL, outline="white", width=2,
            )

        # ── Persistence Diagram canvas ───────────────────────────
        pd_frame = ttk.LabelFrame(main_frame, text="Persistence Diagram")
        pd_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        pd_canvas = tk.Canvas(
            pd_frame, width=self.PD_WIDTH, height=self.PD_HEIGHT,
            bg="#1E1E2E", highlightthickness=0,
        )
        pd_canvas.pack(fill=tk.BOTH, expand=True)

        draw_persistence_diagram(pd_canvas, h0_pairs, h1_pairs, max_dist)

        # ── Slider update ────────────────────────────────────────
        def update_vr(*_):
            alpha = alpha_var.get()
            alpha_label.config(text=f"{alpha:.1f}")

            vr_canvas.delete("vr_edge")
            for d, i, j in dist_pairs:
                if d > alpha:
                    break
                sx1, sy1 = scaled_positions[i]
                sx2, sy2 = scaled_positions[j]
                vr_canvas.create_line(
                    sx1, sy1, sx2, sy2,
                    fill="#FFD700", width=2, tags="vr_edge",
                )

            b0, b1 = self.vr.betti_numbers(alpha)
            b0_label.config(text=str(b0))
            b1_label.config(text=str(b1))

            pd_canvas.delete("marker")
            pd_margin = 30
            pd_w = self.PD_WIDTH - 2 * pd_margin
            pd_h = self.PD_HEIGHT - 2 * pd_margin
            plot_max = max_dist * 1.6
            if plot_max > 0:
                ax = pd_margin + (alpha / plot_max) * pd_w
                ay = pd_margin + pd_h - (alpha / plot_max) * pd_h
                pd_canvas.create_oval(
                    ax - 5, ay - 5, ax + 5, ay + 5,
                    fill="white", outline="white", tags="marker",
                )

        alpha_var.trace_add("write", update_vr)
        alpha_var.set(0)

        def animate_growth():
            steps = [d for d, _, _ in dist_pairs]
            if not steps:
                return

            def step_forward(idx):
                if idx < len(steps):
                    alpha_var.set(steps[idx])
                    self.win.after(150, step_forward, idx + 1)

            self.win.after(100, step_forward, 0)

        ttk.Button(top_frame, text="▶ Animate Growth", command=animate_growth).pack(
            side=tk.RIGHT, padx=5,
        )

