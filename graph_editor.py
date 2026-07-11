#!/usr/bin/env python3
"""
Graph Editor - Click to add nodes, click node to node to create edges.

Controls:
  - Left click on empty space          : Add a new node
  - Left click on a node               : Select it (highlighted in red)
  - Left click on another node while
    one is selected                    : Create a directed edge
  - Left click on the same node again  : Deselect it
  - Left drag on a node                : Move the node
  - Right click on a node              : Delete the node and its edges
  - Right click on an edge             : Delete the edge
  - Delete key                         : Delete selected/hovered node
  - Ctrl+Z                             : Undo (remove last added node)
"""

import base64
import io
import json
import math
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen
from urllib.error import URLError

import numpy as np

# ── Logging ────────────────────────────────────────────────────────
try:
    from utils.logger import get_logger, setup_logging
    setup_logging()
    log = get_logger(__name__)
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.setLevel(logging.WARNING)

# ── Power grid electrical distance modules ──────────────────
try:
    from electrical_distance.ptdf_calculator import (
        compute_ptdf,
        compute_lodf,
        compute_effective_resistance_matrix,
        compute_ptdf_vector_distance,
    )
    from electrical_distance.metrics import (
        PTDFVectorDistance,
        EffectiveResistanceDistance,
        KCLCurrentDistance,
    )
    from tda.vr_core import VRComplex
    from tda.vulnerability import (
        compute_vulnerability_scores,
        rank_vulnerable_buses,
        compute_vulnerability_summary,
    )
    from integration.grid_to_graph import GridGraphConverter
    from integration.power_grid_tda import PowerGridTDAExplorer, METRICS
    from power_grid.importer import load_grid, get_test_grid_3bus, get_test_grid_5bus
    from power_grid.ukraine_loader import get_ukraine_330kv_grid, get_large_ukraine_grid
    _HAS_ELEC = True
except ImportError:
    _HAS_ELEC = False


class Node:
    """Represents a single node in the graph."""

    RADIUS = 20
    COLOR_NORMAL = "#4A90D9"
    COLOR_HOVER = "#6DB3F8"
    COLOR_SELECTED = "#FF6B6B"
    FONT = ("Helvetica", 10, "bold")

    def __init__(self, canvas, x, y, label=None):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.label = label or ""
        self.edges = []  # list of Edge objects connected to this node
        self.radius = Node.RADIUS
        self.color = Node.COLOR_NORMAL

        self._id = None  # canvas oval id
        self._text_id = None  # canvas text id
        self._draw()

    def _draw(self):
        """Draw the node (circle + label) on the canvas."""
        r = self.radius
        self._id = self.canvas.create_oval(
            self.x - r,
            self.y - r,
            self.x + r,
            self.y + r,
            fill=self.color,
            outline="white",
            width=2,
            tags=("node",),
        )
        display_text = self.label if self.label else ""
        self._text_id = self.canvas.create_text(
            self.x,
            self.y,
            text=display_text,
            font=Node.FONT,
            fill="white",
            tags=("node_label",),
        )

    def update_position(self, x, y):
        """Move the node to a new position and redraw connected edges."""
        self.x = x
        self.y = y
        self.canvas.coords(
            self._id, x - self.radius, y - self.radius, x + self.radius, y + self.radius
        )
        self.canvas.coords(self._text_id, x, y)
        for edge in self.edges:
            edge.redraw()

    def set_color(self, color):
        """Change the fill color of the node."""
        self.color = color
        self.canvas.itemconfig(self._id, fill=color)

    def contains_point(self, x, y):
        """Check if (x, y) is inside this node."""
        dx = self.x - x
        dy = self.y - y
        return dx * dx + dy * dy <= self.radius * self.radius

    def delete(self):
        """Remove the node's canvas items."""
        self.canvas.delete(self._id)
        self.canvas.delete(self._text_id)

    def __repr__(self):
        return f"Node({self.label or '?'}, {self.x}, {self.y})"


class Edge:
    """Represents a directed edge between two Node objects."""

    COLOR_NORMAL = "#888888"
    COLOR_HOVER = "#AAAAAA"
    ARROW_SIZE = 10
    WIDTH = 2

    def __init__(self, canvas, source, target, label=None):
        self.canvas = canvas
        self.source = source
        self.target = target
        self.label = label or ""
        self.color = Edge.COLOR_NORMAL

        self._line_id = None
        self._arrow_id = None
        self._label_id = None
        self._draw()

        # Register this edge with both nodes
        source.edges.append(self)
        target.edges.append(self)

    def _draw(self):
        """Draw the edge as a line with an arrowhead."""
        x1, y1 = self.source.x, self.source.y
        x2, y2 = self.target.x, self.target.y

        # Calculate arrow direction
        dx = x2 - x1
        dy = y2 - y1
        dist = (dx * dx + dy * dy) ** 0.5
        if dist == 0:
            dist = 1
        ux, uy = dx / dist, dy / dist

        # Shrink line to stop at node borders
        r = Node.RADIUS
        sx = x1 + ux * r
        sy = y1 + uy * r
        tx = x2 - ux * r
        ty = y2 - uy * r

        # Line
        self._line_id = self.canvas.create_line(
            sx, sy, tx, ty, fill=self.color, width=Edge.WIDTH, tags=("edge",)
        )

        # Arrowhead
        ax = self.ARROW_SIZE
        p1_x = tx + ux * ax - uy * ax * 0.5
        p1_y = ty + uy * ax + ux * ax * 0.5
        p2_x = tx + ux * ax + uy * ax * 0.5
        p2_y = ty + uy * ax - ux * ax * 0.5
        self._arrow_id = self.canvas.create_polygon(
            tx,
            ty,
            p1_x,
            p1_y,
            p2_x,
            p2_y,
            fill=self.color,
            outline=self.color,
            tags=("edge_arrow",),
        )

        # Label in the middle of the edge
        if self.label:
            mx, my = (sx + tx) / 2, (sy + ty) / 2
            self._label_id = self.canvas.create_text(
                mx,
                my,
                text=self.label,
                font=("Helvetica", 9),
                fill="#CCCCCC",
                tags=("edge_label",),
            )

    def redraw(self):
        """Redraw the edge after node movement."""
        self.canvas.delete(self._line_id)
        self.canvas.delete(self._arrow_id)
        if self._label_id:
            self.canvas.delete(self._label_id)
        self._draw()

    def set_color(self, color):
        """Change the color of the edge."""
        self.color = color
        self.canvas.itemconfig(self._line_id, fill=color)
        self.canvas.itemconfig(self._arrow_id, fill=color)

    def delete(self):
        """Remove the edge's canvas items and unregister from nodes."""
        self.canvas.delete(self._line_id)
        self.canvas.delete(self._arrow_id)
        if self._label_id:
            self.canvas.delete(self._label_id)
        if self in self.source.edges:
            self.source.edges.remove(self)
        if self in self.target.edges:
            self.target.edges.remove(self)

    def __repr__(self):
        return f"Edge({self.source} -> {self.target})"


class GraphEditor:
    """Main application class for the graph editor."""

    CANVAS_WIDTH = 900
    CANVAS_HEIGHT = 600
    BG_COLOR = "#1E1E2E"
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, root):
        self.root = root
        self.root.title("그래프 편집기")
        self.root.geometry(f"{self.CANVAS_WIDTH}x{self.CANVAS_HEIGHT + 50}")
        self.root.configure(bg="#1E1E2E")

        self.nodes = []  # all Node objects
        self.edges = []  # all Edge objects

        # Interaction state
        self.selected_node = None
        self.dragging_node = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.hovered_node = None
        self.hovered_edge = None

        # Node counter for auto-labeling
        self.node_counter = 0

        # API key (prompted on first use)
        self._api_key = None

        # Power grid data (for electrical distance analysis)
        self._grid_converter = None
        self._power_grid_data = None

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        """Build the toolbar and canvas."""
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Label(
            toolbar,
            text="클릭: 노드 선택  |  "
            "선택 → 다른 노드 클릭: 간선  |  "
            "드래그: 노드 이동  |  "
            "우클릭: 삭제",
        ).pack(side=tk.LEFT)

        ttk.Button(toolbar, text="⚡ 전력망 임포트", command=self._import_power_grid).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(toolbar, text="전체 삭제", command=self._clear_all).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(toolbar, text="그래프 정보 내보내기", command=self._export_info).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(toolbar, text="🔬 TDA Distance", command=self._open_power_grid_tda).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(toolbar, text="📊 TDA 탐색기", command=self._tda_explorer).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(toolbar, text="⚠ 취약점 분석", command=self._vulnerability_analysis).pack(
            side=tk.RIGHT, padx=5
        )

        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            bg=self.BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _bind_events(self):
        """Bind mouse and keyboard events."""
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<Control-z>", self._on_undo)

        self.canvas.tag_bind("node", "<Enter>", self._on_node_enter)
        self.canvas.tag_bind("node", "<Leave>", self._on_node_leave)
        self.canvas.tag_bind("edge", "<Enter>", self._on_edge_enter)
        self.canvas.tag_bind("edge", "<Leave>", self._on_edge_leave)

    # ─── Node / Edge Management ──────────────────────────────────

    def add_node(self, x, y, label=None):
        """Create a new node at (x, y) with an optional label."""
        if not label:
            self.node_counter += 1
            label = str(self.node_counter)
        node = Node(self.canvas, x, y, label)
        self.nodes.append(node)
        return node

    def add_edge(self, source, target, label=None):
        """Create an edge between two nodes. Avoids duplicates."""
        for edge in self.edges:
            if edge.source is source and edge.target is target:
                return edge
        edge = Edge(self.canvas, source, target, label)
        self.edges.append(edge)
        return edge

    def remove_node(self, node):
        """Delete a node and all its connected edges."""
        if node not in self.nodes:
            return
        if self.selected_node is node:
            self.selected_node = None
        if self.hovered_node is node:
            self.hovered_node = None
        for edge in list(node.edges):
            self.remove_edge(edge)
        node.delete()
        self.nodes.remove(node)

    def remove_edge(self, edge):
        """Delete a specific edge."""
        if edge not in self.edges:
            return
        if self.hovered_edge is edge:
            self.hovered_edge = None
        edge.delete()
        self.edges.remove(edge)

    def _clear_all(self):
        """Remove all nodes and edges."""
        if not self.nodes and not self.edges:
            return
        if not messagebox.askyesno("모두 지우기", "모든 노드와 엣지를 삭제하시겠습니까?"):
            return
        for edge in list(self.edges):
            edge.delete()
        self.edges.clear()
        for node in list(self.nodes):
            node.delete()
        self.nodes.clear()
        self.node_counter = 0
        self.selected_node = None
        self.hovered_node = None
        self.hovered_edge = None

    def _export_info(self):
        """Show graph info in a message box."""
        node_count = len(self.nodes)
        edge_count = len(self.edges)
        msg = f"노드: {node_count}\n엣지: {edge_count}\n\n"
        msg += "=== 엣지 목록 ===\n"
        for i, edge in enumerate(self.edges):
            msg += f"{i + 1}. {edge.source.label} → {edge.target.label}\n"
        messagebox.showinfo("그래프 정보", msg)

    # ─── Power Grid Import ────────────────────────────────────

    def _import_power_grid(self):
        """Import a power grid from a file or built-in test case."""
        if not _HAS_ELEC:
            messagebox.showerror(
                "Import Error",
                "Electrical distance modules not loaded.\n"
                "Run from the graph_editor package directory.",
            )
            return

        win = tk.Toplevel(self.root)
        win.title("전력망 임포트")
        win.geometry("500x300")
        win.configure(bg="#1E1E2E")

        ttk.Label(win, text="전력망 데이터 소스 선택", font=("Helvetica", 12, "bold")).pack(pady=10)

        def load_test_grid(name, grid_fn):
            grid_data = grid_fn()
            self._load_grid_data(grid_data)
            win.destroy()
            messagebox.showinfo(
                "임포트 완료",
                f"'{name}' 전력망을 임포트했습니다.\n"
                f"버스: {len(grid_data['buses'])}개\n"
                f"선로: {len(grid_data['lines'])}개",
            )

        ttk.Button(
            win,
            text="3-Bus 테스트",
            command=lambda: load_test_grid("3-Bus", get_test_grid_3bus),
        ).pack(pady=5)
        # ── Ukraine grid ──────────────────────────────────────────
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(win, text="🇺🇦 우크라이나 전력망", font=("Helvetica", 10)).pack(pady=2)

        ttk.Button(
            win,
            text="18-Bus (330 kV Backbone)",
            command=lambda: load_test_grid("18-Bus Ukraine", get_ukraine_330kv_grid),
        ).pack(pady=3)
        ttk.Button(
            win,
            text="28-Bus (330/220 kV 확장)",
            command=lambda: load_test_grid("28-Bus Ukraine", get_large_ukraine_grid),
        ).pack(pady=3)

        def load_from_file():
            from tkinter import filedialog

            path = filedialog.askopenfilename(
                title="전력망 파일 선택",
                filetypes=[
                    ("JSON", "*.json"),
                    ("Matpower", "*.m"),
                    ("PyPSA", "*.nc;*.h5"),
                    ("All", "*"),
                ],
            )
            if not path:
                return
            try:
                grid_data = load_grid(path)
                self._load_grid_data(grid_data)
                win.destroy()
                messagebox.showinfo(
                    "임포트 완료",
                    f"'{path}'에서 전력망을 임포트했습니다.\n"
                    f"버스: {len(grid_data['buses'])}개\n"
                    f"선로: {len(grid_data['lines'])}개",
                )
            except Exception as e:
                messagebox.showerror("임포트 실패", str(e))

        ttk.Button(win, text="📁 파일에서 불러오기...", command=load_from_file).pack(pady=5)
        ttk.Button(win, text="취소", command=win.destroy).pack(pady=10)

    def _load_grid_data(self, grid_data):
        """Load grid data into the editor and store electrical params."""
        if _HAS_ELEC:
            self._grid_converter = GridGraphConverter(grid_data)
            self._power_grid_data = grid_data
            self._grid_converter.add_to_editor(self, use_geo_layout=False)

    # ─── Power Grid TDA (Electrical Distance) ────────────────

    def _open_power_grid_tda(self):
        """Open enhanced TDA explorer with electrical distance metrics."""
        if not _HAS_ELEC:
            messagebox.showerror("Error", "Electrical distance modules not available.")
            return

        if self._grid_converter is None:
            result = messagebox.askyesno(
                "전력망 필요",
                "분석할 전력망 데이터가 없습니다.\n"
                "먼저 전력망을 임포트하시겠습니까?\n\n"
                "아니오를 누르면 현재 그래프의 노드로 진행합니다.",
            )
            if result:
                self._import_power_grid()
                if self._grid_converter is None:
                    return
            else:
                if len(self.nodes) < 2:
                    messagebox.showinfo("TDA Distance", "노드가 최소 2개 필요합니다.")
                    return
                self._build_fake_grid_from_graph()

        data = self._grid_converter.get_electrical_data()
        explorer = PowerGridTDAExplorer(self.root, data)
        explorer.open()

    def _build_fake_grid_from_graph(self):
        """Build a fake electrical grid from the current graph for PTDF testing."""
        n = len(self.nodes)
        n_to_idx = {id(n): i for i, n in enumerate(self.nodes)}
        positions = [(n.x, n.y) for n in self.nodes]

        buses = []
        for i, node in enumerate(self.nodes):
            buses.append({
                "id": i,
                "name": node.label,
                "x": node.x,
                "y": node.y,
                "v_nom": 1.0,
            })

        pairs = []
        susc = []
        for edge in self.edges:
            u = n_to_idx.get(id(edge.source))
            v = n_to_idx.get(id(edge.target))
            if u is not None and v is not None:
                pairs.append((u, v))
                dx = positions[u][0] - positions[v][0]
                dy = positions[u][1] - positions[v][1]
                dist = math.sqrt(dx * dx + dy * dy)
                susc.append(1.0 / max(dist / 100, 0.01))

        grid_data = {
            "name": "Current Graph",
            "buses": buses,
            "lines": [
                {
                    "id": i,
                    "name": f"L{i}",
                    "from_bus": f,
                    "to_bus": t,
                    "x": 1.0 / max(s, 1e-6),
                    "r": 0.0,
                    "rate": 100,
                }
                for i, ((f, t), s) in enumerate(zip(pairs, susc))
            ],
            "generators": [{"bus": 0, "p_mw": 100, "name": "Gen"}],
            "loads": [{"bus": n - 1, "p_mw": 100, "name": "Load"}],
            "base_mva": 100.0,
        }
        self._power_grid_data = grid_data
        self._grid_converter = GridGraphConverter(grid_data)

    # ─── TDA 탐색기 ────────────────────────────────────────────

    def _tda_explorer(self):
        """Open the TDA Explorer with VR view, persistence diagram, and AI analysis."""
        n = len(self.nodes)
        if n == 0:
            messagebox.showinfo("TDA 탐색기", "그래프에 노드가 없습니다.\n먼저 노드를 추가하세요!")
            return

        V = n
        points = [(node.x, node.y) for node in self.nodes]

        # Pre-compute VR data
        dist_pairs = []
        for i in range(V):
            for j in range(i + 1, V):
                dx = points[i][0] - points[j][0]
                dy = points[i][1] - points[j][1]
                d = math.sqrt(dx * dx + dy * dy)
                dist_pairs.append((d, i, j))
        dist_pairs.sort()

        unique_dists = sorted({d for d, _, _ in dist_pairs})
        if not unique_dists:
            unique_dists = [0]

        max_dist = unique_dists[-1] if unique_dists else 1
        margin = max_dist * 0.05 or 5

        # Build H0 / H1 persistence pairs (with proper triangle-death computation)
        vr_parent = list(range(V))
        comp_birth = [0.0] * V

        def find(x):
            while vr_parent[x] != x:
                vr_parent[x] = vr_parent[vr_parent[x]]
                x = vr_parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                vr_parent[px] = py

        # Track existing edges and active H1 cycles
        edge_exists: dict[tuple[int, int], float] = {}
        active_cycles: list[tuple[float, tuple[int, int]]] = []

        h0_pairs = []
        h1_pairs = []

        for d, i, j in dist_pairs:
            pi, pj = find(i), find(j)
            if pi != pj:
                if comp_birth[pi] <= comp_birth[pj]:
                    dying, surviving = pj, pi
                else:
                    dying, surviving = pi, pj
                h0_pairs.append((comp_birth[dying], d))
                comp_birth[surviving] = min(comp_birth[surviving], comp_birth[dying])
                union(i, j)
            else:
                # H1: cycle born
                active_cycles.append((d, (i, j)))

            # Record edge
            edge_exists[(i, j)] = d
            edge_exists[(j, i)] = d

            # Check triangles: find k such that (i,k) and (j,k) also exist
            for k in range(V):
                if k == i or k == j:
                    continue
                if (i, k) in edge_exists and (j, k) in edge_exists:
                    d_ik = edge_exists[(i, k)]
                    d_jk = edge_exists[(j, k)]
                    triangle_complete_at = max(d, d_ik, d_jk)

                    # Find youngest active cycle involving any of the three edges
                    candidates = []
                    for idx, (bd, (ei, ej)) in enumerate(active_cycles):
                        if ((ei, ej) in ((i, j), (j, i), (i, k), (k, i), (j, k), (k, j))):
                            candidates.append((bd, idx))

                    if candidates:
                        candidates.sort(key=lambda x: -x[0])
                        _, kill_idx = candidates[0]
                        bd, _ = active_cycles.pop(kill_idx)
                        h1_pairs.append((bd, triangle_complete_at))
                        break  # One triangle kills at most one cycle per edge addition

        infinity = max_dist * 1.5
        for bd, _ in active_cycles:
            h1_pairs.append((bd, infinity))

        survivors = set(find(i) for i in range(V))
        for s in survivors:
            h0_pairs.append((comp_birth[s], infinity))

        # Pre-compute Betti curves
        b0_vals = []
        b1_vals = []

        for alpha in unique_dists:
            p = list(range(V))

            def pp_find(x):
                while p[x] != x:
                    p[x] = p[p[x]]
                    x = p[x]
                return x

            def pp_union(x, y):
                px, py = pp_find(x), pp_find(y)
                if px != py:
                    p[px] = py

            e_count = 0
            for d, i, j in dist_pairs:
                if d <= alpha:
                    pp_union(i, j)
                    e_count += 1
                else:
                    break
            comps = set(pp_find(i) for i in range(V))
            b0 = len(comps)
            b1 = e_count - V + b0
            b0_vals.append(b0)
            b1_vals.append(b1)

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

        # Build the Explorer window
        win = tk.Toplevel(self.root)
        win.title("TDA 탐색기")
        win.geometry("1100x750")
        win.configure(bg="#1E1E2E")

        top_frame = ttk.Frame(win, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="α (거리 임계값):").pack(side=tk.LEFT)
        alpha_var = tk.DoubleVar(value=0)
        alpha_scale = ttk.Scale(
            top_frame,
            from_=0,
            to=unique_dists[-1],
            variable=alpha_var,
            orient=tk.HORIZONTAL,
            length=200,
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

        ai_btn = ttk.Button(top_frame, text="🤖 AI 분석 (딥시크)", command=lambda: self._ask_ai_tda(win))
        ai_btn.pack(side=tk.RIGHT, padx=5)

        stats_label = ttk.Label(
            top_frame,
            text=f"  |  V={V} E={E} χ={euler_char} β₀={beta0_graph} β₁={beta1_graph}",
        )
        stats_label.pack(side=tk.LEFT, padx=10)

        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # VR View canvas
        vr_frame = ttk.LabelFrame(main_frame, text="Vietoris-Rips Complex Growth")
        vr_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        VR_WIDTH = 500
        VR_HEIGHT = 500
        vr_canvas = tk.Canvas(
            vr_frame,
            width=VR_WIDTH,
            height=VR_HEIGHT,
            bg="#1E1E2E",
            highlightthickness=0,
        )
        vr_canvas.pack(fill=tk.BOTH, expand=True)

        VR_MARGIN = 40
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        rx = max(max_x - min_x, 1)
        ry = max(max_y - min_y, 1)

        scaled_positions = []
        for node in self.nodes:
            sx = VR_MARGIN + ((node.x - min_x) / rx) * (VR_WIDTH - 2 * VR_MARGIN)
            sy = VR_MARGIN + ((node.y - min_y) / ry) * (VR_HEIGHT - 2 * VR_MARGIN)
            scaled_positions.append((sx, sy))

        for sx, sy in scaled_positions:
            vr_canvas.create_oval(
                sx - 12,
                sy - 12,
                sx + 12,
                sy + 12,
                fill=Node.COLOR_NORMAL,
                outline="white",
                width=2,
            )

        # Persistence Diagram canvas
        pd_frame = ttk.LabelFrame(main_frame, text="Persistence Diagram")
        pd_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        PD_WIDTH = 450
        PD_HEIGHT = 450
        pd_canvas = tk.Canvas(
            pd_frame,
            width=PD_WIDTH,
            height=PD_HEIGHT,
            bg="#1E1E2E",
            highlightthickness=0,
        )
        pd_canvas.pack(fill=tk.BOTH, expand=True)

        _draw_pd(pd_canvas, h0_pairs, h1_pairs, max_dist)

        # Slider update function
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

            # Update Betti numbers
            p = list(range(V))

            def vf(x):
                while p[x] != x:
                    p[x] = p[p[x]]
                    x = p[x]
                return x

            def vu(x, y):
                px, py = vf(x), vf(y)
                if px != py:
                    p[px] = py

            ec = 0
            for d, i, j in dist_pairs:
                if d > alpha:
                    break
                vu(i, j)
                ec += 1
            comps = set(vf(i) for i in range(V))
            b0 = len(comps)
            b1 = ec - V + b0
            b0_label.config(text=str(b0))
            b1_label.config(text=str(b1))

            pd_canvas.delete("marker")
            pd_margin = 30
            pd_w = PD_WIDTH - 2 * pd_margin
            pd_h = PD_HEIGHT - 2 * pd_margin
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
                    win.after(150, step_forward, idx + 1)

            win.after(100, step_forward, 0)

        ttk.Button(top_frame, text="▶ Animate Growth", command=animate_growth).pack(
            side=tk.RIGHT, padx=5
        )

    # ─── AI Analysis via OpenRouter ──────────────────────────────

    def _ask_ai_tda(self, parent_win):
        """Send graph diagram + TDA data to DeepSeek (via OpenRouter) for interpretation."""
        if not self._api_key:
            key_win = tk.Toplevel(parent_win)
            key_win.title("OpenRouter API Key")
            key_win.geometry("400x120")
            key_win.configure(bg="#1E1E2E")

            ttk.Label(key_win, text="Enter your OpenRouter API key:").pack(pady=(10, 5))
            key_entry = ttk.Entry(key_win, width=50, show="*")
            key_entry.pack(pady=5)

            def save_key():
                self._api_key = key_entry.get().strip()
                if self._api_key:
                    key_win.destroy()
                    self._do_ask_ai(parent_win)

            ttk.Button(key_win, text="Save & Continue", command=save_key).pack(pady=5)
            key_win.grab_set()
            return

        self._do_ask_ai(parent_win)

    def _do_ask_ai(self, parent_win):
        """Make the API call in a background thread."""
        loading = tk.Toplevel(parent_win)
        loading.title("Thinking...")
        loading.geometry("300x80")
        loading.configure(bg="#1E1E2E")
        ttk.Label(loading, text="🤖 Analyzing with DeepSeek...").pack(pady=20)
        loading.grab_set()

        # Track whether loading window is still alive
        loading_active = True

        def on_loading_close():
            nonlocal loading_active
            loading_active = False
            loading.grab_release()
            loading.destroy()

        loading.protocol("WM_DELETE_WINDOW", on_loading_close)

        img_base64 = None
        try:
            ps_data = self.canvas.postscript(colormode="color")
            if ps_data and ps_data.strip():
                try:
                    from PIL import Image

                    ps_buf = io.BytesIO(ps_data.encode("utf-8"))
                    img = Image.open(ps_buf)
                    png_buf = io.BytesIO()
                    img.save(png_buf, format="PNG")
                    img_base64 = base64.b64encode(png_buf.getvalue()).decode("utf-8")
                except ImportError:
                    # PIL not installed — image capture skipped, text-only analysis
                    pass
                except Exception:
                    # PostScript data might be corrupt or canvas not ready
                    pass
            else:
                # Empty PostScript — canvas likely not rendered yet
                pass
        except Exception:
            # Canvas postscript() call failed (e.g. no display, offscreen)
            pass

        V = len(self.nodes)
        E = len(self.edges)
        node_data = [
            {"label": node.label, "x": round(node.x, 1), "y": round(node.y, 1)}
            for node in self.nodes
        ]
        edge_data = [
            {"from": edge.source.label, "to": edge.target.label}
            for edge in self.edges
        ]

        parent = list(range(V))

        def uf_find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def uf_union(x, y):
            px, py = uf_find(x), uf_find(y)
            if px != py:
                parent[px] = py

        node_to_idx = {id(node): i for i, node in enumerate(self.nodes)}
        for edge in self.edges:
            u = node_to_idx.get(id(edge.source))
            v = node_to_idx.get(id(edge.target))
            if u is not None and v is not None:
                uf_union(u, v)
        comps = set(uf_find(i) for i in range(V))
        beta0 = len(comps)
        beta1 = E - V + beta0
        euler_char = V - E

        system_msg = (
            "You are a topologist AI. Analyze the graph shown in the image and the "
            "accompanying topological data. Explain:\n"
            "1. What topological features does this graph have?\n"
            "2. What manifold or shape might this represent?\n"
            "3. Is there anything mathematically interesting about its structure?\n"
            "Be concise but insightful.\n"
            "Please respond in Korean."
        )

        user_content = []
        if img_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
            })
        user_content.append({
            "type": "text",
            "text": (
                f"Here is the topological data for this graph:\n"
                f"- Vertices: {V}\n"
                f"- Edges: {E}\n"
                f"- Euler characteristic (χ = V - E): {euler_char}\n"
                f"- β₀ (connected components): {beta0}\n"
                f"- β₁ (independent cycles): {beta1}\n\n"
                f"Node positions:\n{json.dumps(node_data, indent=2)}\n\n"
                f"Edges:\n{json.dumps(edge_data, indent=2)}\n\n"
                "Please analyze the topological structure of this graph."
            ),
        })

        payload_data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 2048,
        }

        def api_call():
            try:
                payload = json.dumps(payload_data).encode()
                req = Request(
                    self.OPENROUTER_API_URL,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/graph-editor",
                        "X-Title": "Graph Editor TDA",
                    },
                )
                resp = urlopen(req, timeout=120)
                data = json.loads(resp.read())
                reply = data["choices"][0]["message"]["content"]
                if loading_active:
                    parent_win.after(0, lambda: self._show_ai_result(parent_win, reply, loading))
            except URLError as exc:
                if loading_active:
                    parent_win.after(0, lambda e=str(exc): self._show_ai_error(parent_win, e, loading))
            except Exception as exc:
                if loading_active:
                    parent_win.after(0, lambda e=str(exc): self._show_ai_error(parent_win, e, loading))

        thread = threading.Thread(target=api_call, daemon=True)
        thread.start()

    def _show_ai_result(self, parent_win, reply, loading_win):
        """Display the AI analysis result."""
        try:
            if loading_win.winfo_exists():
                loading_win.grab_release()
                loading_win.destroy()
        except tk.TclError:
            pass
        result_win = tk.Toplevel(parent_win)
        result_win.title("🤖 DeepSeek Analysis")
        result_win.geometry("600x500")
        result_win.configure(bg="#1E1E2E")

        text_frame = ttk.Frame(result_win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            bg="#1E1E2E",
            fg="#FFFFFF",
            font=("Helvetica", 11),
            padx=10,
            pady=10,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_widget.insert(tk.END, reply)
        text_widget.config(state=tk.DISABLED)

        ttk.Button(result_win, text="Close", command=result_win.destroy).pack(pady=5)

    def _show_ai_error(self, parent_win, error_msg, loading_win):
        """Show an API error to the user."""
        try:
            if loading_win.winfo_exists():
                loading_win.grab_release()
                loading_win.destroy()
        except tk.TclError:
            pass
        messagebox.showerror("API Error", f"Failed to get AI analysis:\n\n{error_msg}")

    # ─── Event Handlers ──────────────────────────────────────────

    def get_node_at(self, x, y):
        """Return the top-most node containing (x, y), or None."""
        for node in reversed(self.nodes):
            if node.contains_point(x, y):
                return node
        return None

    def get_edge_near(self, x, y, threshold=10):
        """Find an edge close to (x, y)."""
        for edge in reversed(self.edges):
            x1, y1 = edge.source.x, edge.source.y
            x2, y2 = edge.target.x, edge.target.y
            dist = self._point_to_segment_dist(x, y, x1, y1, x2, y2)
            if dist <= threshold:
                return edge
        return None

    @staticmethod
    def _point_to_segment_dist(px, py, x1, y1, x2, y2):
        """Distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        near_x = x1 + t * dx
        near_y = y1 + t * dy
        return ((px - near_x) ** 2 + (py - near_y) ** 2) ** 0.5

    def _clear_selected_node(self):
        """Deselect the currently selected node."""
        if self.selected_node:
            self.selected_node.set_color(Node.COLOR_NORMAL)
            self.selected_node = None

    def _on_left_click(self, event):
        """Handle left mouse button press."""
        x, y = event.x, event.y
        node = self.get_node_at(x, y)

        if node:
            self.dragging_node = node
            self.drag_start_x = x
            self.drag_start_y = y

            if self.selected_node and self.selected_node is not node:
                self.add_edge(self.selected_node, node)
                self._clear_selected_node()
            else:
                if self.selected_node is node:
                    self._clear_selected_node()
                else:
                    self._clear_selected_node()
                    self.selected_node = node
                    node.set_color(Node.COLOR_SELECTED)
        else:
            self._clear_selected_node()
            self.add_node(x, y)

    def _on_left_drag(self, event):
        """Handle mouse drag while left button is held."""
        x, y = event.x, event.y
        if self.dragging_node:
            self.dragging_node.update_position(x, y)

    def _on_left_release(self, event):
        """Handle left mouse button release."""
        self.dragging_node = None

    def _on_right_click(self, event):
        """Handle right mouse button press to delete items."""
        x, y = event.x, event.y
        node = self.get_node_at(x, y)
        if node:
            self.remove_node(node)
            return
        edge = self.get_edge_near(x, y)
        if edge:
            self.remove_edge(edge)
            return

    def _on_mouse_move(self, event):
        """Handle mouse movement for hover effects."""
        x, y = event.x, event.y
        node = self.get_node_at(x, y)
        if node and node is not self.hovered_node:
            if self.hovered_node and self.hovered_node is not self.selected_node:
                self.hovered_node.set_color(Node.COLOR_NORMAL)
            self.hovered_node = node
            if node is not self.selected_node:
                node.set_color(Node.COLOR_HOVER)
        elif not node and self.hovered_node:
            if self.hovered_node is not self.selected_node:
                self.hovered_node.set_color(Node.COLOR_NORMAL)
            self.hovered_node = None

    def _on_node_enter(self, event):
        pass  # handled by _on_mouse_move

    def _on_node_leave(self, event):
        pass  # handled by _on_mouse_move

    def _on_edge_enter(self, event):
        x, y = event.x, event.y
        edge = self.get_edge_near(x, y)
        if edge:
            self.hovered_edge = edge
            edge.set_color(Edge.COLOR_HOVER)

    def _on_edge_leave(self, event):
        if self.hovered_edge:
            self.hovered_edge.set_color(Edge.COLOR_NORMAL)
            self.hovered_edge = None

    def _on_delete_key(self, event):
        """Delete key removes selected node, or hovered node as fallback."""
        if self.selected_node:
            node = self.selected_node
            self._clear_selected_node()
            self.remove_node(node)
        elif self.hovered_node:
            self.remove_node(self.hovered_node)
            self.hovered_node = None

    def _on_undo(self, event):
        """Ctrl+Z removes the last added node."""
        if self.nodes:
            node = self.nodes[-1]
            self.remove_node(node)

    # ─── Vulnerability Analysis ──────────────────────────────────

    def _vulnerability_analysis(self):
        """Open vulnerability analysis window using persistence homology.

        Builds distance matrix (electrical if grid data available, else
        Euclidean from node positions), computes VR complex, derives
        vulnerability scores, color-codes nodes on the canvas, and
        displays a ranked result window.
        """
        if len(self.nodes) < 2:
            messagebox.showwarning(
                "경고", "취약점 분석을 위해 최소 2개 이상의 노드가 필요합니다."
            )
            return

        # ── 1. Build distance matrix ────────────────────────────────
        bus_labels = [n.label or f"Node{i}" for i, n in enumerate(self.nodes)]

        if self._grid_converter is not None and self._power_grid_data is not None:
            dist_matrix = self._build_electrical_distance_matrix()
            if dist_matrix is None:
                return
            buses = self._power_grid_data.get("buses", [])
            if len(buses) == len(self.nodes):
                bus_labels = [
                    b.get("name") or f"Bus{b['id']}" for b in buses
                ]
        else:
            dist_matrix = self._build_euclidean_distance_matrix()

        if dist_matrix is None:
            return

        # ── 2. Compute VR complex ──────────────────────────────────
        try:
            vr = VRComplex(dist_matrix)
        except Exception as e:
            messagebox.showerror("오류", f"VR 복합체 계산 중 오류: {e}")
            return

        # ── 3. Compute vulnerability scores ─────────────────────────
        try:
            scores = compute_vulnerability_scores(dist_matrix, vr)
            summary = compute_vulnerability_summary(
                dist_matrix, vr, bus_labels, top_k=10
            )
        except Exception as e:
            messagebox.showerror("오류", f"취약점 점수 계산 중 오류: {e}")
            return

        # ── 4. Color nodes on canvas ────────────────────────────────
        self._color_nodes_by_score(scores)

        # ── 5. Show results window ─────────────────────────────────
        self._show_vulnerability_window(scores, summary, vr, dist_matrix, bus_labels)

    def _build_euclidean_distance_matrix(self):
        """Build Euclidean distance matrix from node positions."""
        n = len(self.nodes)
        if n < 2:
            return None
        D = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                dx = self.nodes[i].x - self.nodes[j].x
                dy = self.nodes[i].y - self.nodes[j].y
                d = np.sqrt(dx * dx + dy * dy)
                D[i, j] = d
                D[j, i] = d
        return D

    def _build_electrical_distance_matrix(self):
        """Build electrical distance matrix from grid data (PTDF-based)."""
        try:
            data = self._grid_converter.get_electrical_data()
            n = data["n_bus"]
            bus_pairs = data["bus_pairs"]
            susceptances = data["susceptances"]
            slack = 0

            from electrical_distance.ptdf_calculator import (
                compute_ptdf, compute_ptdf_vector_distance,
            )
            PTDF = compute_ptdf(n, bus_pairs, susceptances, slack)
            return compute_ptdf_vector_distance(PTDF)
        except Exception as e:
            messagebox.showwarning(
                "전기거리 실패",
                f"전기거리 계산 실패 ({e}), 좌표 거리로 대체합니다.",
            )
            return self._build_euclidean_distance_matrix()

    def _color_nodes_by_score(self, scores: np.ndarray):
        """Color nodes on canvas: red (vulnerable) → yellow → green (safe)."""
        s_min, s_max = scores.min(), scores.max()
        if s_max > s_min:
            norm = (scores - s_min) / (s_max - s_min)
        else:
            norm = np.zeros_like(scores)

        for i, node in enumerate(self.nodes):
            if i < len(norm):
                t = norm[i]
                r = int(255 * t)
                g = int(255 * (1 - t))
                b = 0
                color = f"#{r:02x}{g:02x}{b:02x}"
                node.set_color(color)

    def _reset_node_colors(self):
        """Reset all node colors to default (light blue)."""
        for node in self.nodes:
            node.set_color("#ADD8E6")

    def _show_vulnerability_window(
        self,
        scores: np.ndarray,
        summary: dict,
        vr: "VRComplex",
        dist_matrix: np.ndarray,
        bus_labels: list[str],
    ):
        """Display vulnerability analysis results in a new window."""
        win = tk.Toplevel(self.root)
        win.title("⚠ 취약점 분석 결과")
        win.geometry("750x650")
        win.configure(bg="#1E1E2E")

        # ── Title ──────────────────────────────────────────────────
        title_frame = tk.Frame(win, bg="#1E1E2E")
        title_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        grid_name = "수동 그래프"
        if self._power_grid_data:
            grid_name = self._power_grid_data.get("name", "전력망")
        tk.Label(
            title_frame,
            text=f"⚠ 취약점 분석: {grid_name}",
            font=("Helvetica", 16, "bold"),
            bg="#1E1E2E", fg="#FFFFFF",
        ).pack(anchor=tk.W)

        # ── Summary stats ──────────────────────────────────────────
        stats_frame = tk.Frame(win, bg="#1E1E2E")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        b0 = summary.get("overall_beta0", 0)
        b1 = summary.get("overall_beta1", 0)
        n_buses = summary.get("n_buses", 0)
        n_high = summary.get("n_vulnerable_high", 0)
        n_medium = summary.get("n_vulnerable_medium", 0)

        stats_text = (
            f"총 버스: {n_buses}개  |  "
            f"β₀ = {b0}  |  "
            f"β₁ = {b1}  |  "
            f"취약(높음): {n_high}개  |  "
            f"취약(중간): {n_medium}개"
        )
        tk.Label(
            stats_frame,
            text=stats_text,
            font=("Consolas", 11),
            bg="#1E1E2E", fg="#CDD6F4",
        ).pack(anchor=tk.W)

        # ── Legend ─────────────────────────────────────────────────
        legend_frame = tk.Frame(win, bg="#1E1E2E")
        legend_frame.pack(fill=tk.X, padx=10, pady=2)

        for color, label in [
            ("#FF0000", "취약 (높음)"),
            ("#FFAA00", "취약 (중간)"),
            ("#00CC00", "안전"),
        ]:
            f = tk.Frame(legend_frame, bg="#1E1E2E")
            f.pack(side=tk.LEFT, padx=(0, 15))
            c = tk.Canvas(f, width=16, height=16, bg="#1E1E2E",
                          highlightthickness=0)
            c.create_rectangle(2, 2, 14, 14, fill=color, outline="#888888")
            c.pack(side=tk.LEFT)
            tk.Label(f, text=label, font=("Helvetica", 9),
                     bg="#1E1E2E", fg="#CDD6F4").pack(side=tk.LEFT, padx=3)

        # ── Ranked table ───────────────────────────────────────────
        table_frame = tk.Frame(win, bg="#1E1E2E")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        list_frame = tk.Frame(table_frame, bg="#1E1E2E")
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 10),
            bg="#2A2A3E", fg="#FFFFFF",
            selectbackground="#4A4A6E",
            relief=tk.FLAT, borderwidth=0,
            height=15,
        )
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Header
        listbox.insert(tk.END, f"{'순위':>4}  {'버스':<20}  {'점수':>6}  {'상태'}")
        listbox.insert(tk.END, "─" * 55)
        listbox.itemconfig(tk.END, fg="#888888")

        ranked = summary.get("ranked", [])
        for rank, (idx, score, label) in enumerate(ranked, 1):
            if score > 0.7:
                status = "⚠ 위험"
            elif score > 0.4:
                status = "⚡ 주의"
            else:
                status = "✓ 안전"
            text = f"{rank:>4}  {label:<20}  {score:>6.3f}  {status}"
            listbox.insert(tk.END, text)
            if score > 0.7:
                listbox.itemconfig(tk.END, fg="#FF6B6B")
            elif score > 0.4:
                listbox.itemconfig(tk.END, fg="#FFD93D")
            else:
                listbox.itemconfig(tk.END, fg="#6BCB77")

        # ── Bottom buttons ─────────────────────────────────────────
        btn_frame = tk.Frame(win, bg="#1E1E2E")
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        def reset_colors():
            self._reset_node_colors()

        def show_pd():
            self._show_vulnerability_pd(scores, summary, vr, dist_matrix, bus_labels)

        tk.Button(
            btn_frame, text="🔄 색상 초기화", command=reset_colors,
            bg="#3A3A5E", fg="#FFFFFF", relief=tk.FLAT, padx=10,
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            btn_frame, text="📊 지속성 다이어그램", command=show_pd,
            bg="#3A3A5E", fg="#FFFFFF", relief=tk.FLAT, padx=10,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="닫기", command=win.destroy,
            bg="#3A3A5E", fg="#FFFFFF", relief=tk.FLAT, padx=10,
        ).pack(side=tk.RIGHT)

        # ── Tooltip ────────────────────────────────────────────────
        info_frame = tk.Frame(win, bg="#1E1E2E")
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(
            info_frame,
            text="💡 취약점 점수는 지속성 호몰로지 기반: "
                 "고립도(Isolation) + 병합 중요도(Component Merge) - 사이클 완화(Cycle)\n"
                 "빨간색일수록 취약, 녹색일수록 안전합니다.",
            font=("Helvetica", 9),
            bg="#1E1E2E", fg="#A0A0B0", justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _show_vulnerability_pd(
        self,
        scores: np.ndarray,
        summary: dict,
        vr: "VRComplex",
        dist_matrix: np.ndarray,
        bus_labels: list[str],
    ):
        """Show persistence diagram with vulnerability overlay."""
        pd_win = tk.Toplevel(self.root)
        pd_win.title("취약점 지속성 다이어그램")
        pd_win.geometry("600x650")
        pd_win.configure(bg="#1E1E2E")

        h0_pairs, h1_pairs = vr.persistence_pairs()
        max_dist = float(vr.max_distance)

        canvas = tk.Canvas(
            pd_win, bg="#1E1E2E", highlightthickness=0,
            width=550, height=550,
        )
        canvas.pack(padx=10, pady=10)

        _draw_pd(canvas, h0_pairs, h1_pairs, max_dist, width=550, height=550)

        info = tk.Label(
            pd_win,
            text=f"β₀ = {summary['overall_beta0']}  |  "
                 f"β₁ = {summary['overall_beta1']}  |  "
                 f"취약(높음): {summary['n_vulnerable_high']}  |  "
                 f"취약(중간): {summary['n_vulnerable_medium']}",
            font=("Consolas", 11), bg="#1E1E2E", fg="#CDD6F4",
        )
        info.pack(pady=(0, 5))

        tk.Button(
            pd_win, text="닫기", command=pd_win.destroy,
            bg="#3A3A5E", fg="#FFFFFF", relief=tk.FLAT, padx=10,
        ).pack(pady=(0, 10))


# ─── Module-level helper: draw persistence diagram ─────────────

def _draw_pd(canvas, h0_pairs, h1_pairs, max_dist, width=450, height=450):
    """Draw a persistence diagram on a tkinter Canvas."""
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
        text="Death (α)", fill="#AAAAAA", font=("Helvetica", 9),
        angle=90,
    )

    canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#555555")
    canvas.create_line(margin, margin, margin, height - margin, fill="#555555")

    canvas.create_line(
        margin, height - margin,
        margin + pd_w, margin,
        fill="#444444",
        dash=(4, 4),
    )

    if plot_max <= 0:
        return

    def to_canvas(b, d):
        x = margin + (b / plot_max) * pd_w
        y = margin + pd_h - (d / plot_max) * pd_h
        return x, y

    for b, d in h0_pairs:
        cx, cy = to_canvas(b, d)
        canvas.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill="#4A90D9", outline="#4A90D9", tags="pd_point",
        )

    for b, d in h1_pairs:
        cx, cy = to_canvas(b, d)
        canvas.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill="#FF6B6B", outline="#FF6B6B", tags="pd_point",
        )

    canvas.create_oval(margin + 10, margin + 5, margin + 16, margin + 11, fill="#4A90D9", outline="")
    canvas.create_text(margin + 22, margin + 8, text="H₀", fill="#AAAAAA", font=("Helvetica", 9), anchor=tk.W)
    canvas.create_oval(margin + 10, margin + 20, margin + 16, margin + 26, fill="#FF6B6B", outline="")
    canvas.create_text(margin + 22, margin + 23, text="H₁", fill="#AAAAAA", font=("Helvetica", 9), anchor=tk.W)


def main():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")
    app = GraphEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
