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

import math
import tkinter as tk
from tkinter import messagebox, ttk

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

# ── Core domain classes (extracted) ───────────────────────────
from core.node import Node
from core.edge import Edge

# ── UI components (extracted) ─────────────────────────────────
from ui.persistence_diagram import draw_persistence_diagram
from ui.tda_explorer import TdaExplorerWindow
from ui.vulnerability_window import show_vulnerability_window

# ── Analysis modules (extracted) ──────────────────────────────
from analysis.ai_analysis import AiAnalyzer

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


class GraphEditor:
    """Main application class for the graph editor."""

    CANVAS_WIDTH = 900
    CANVAS_HEIGHT = 600
    BG_COLOR = "#1E1E2E"

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

    # ─── UI Build ──────────────────────────────────────────────

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
            side=tk.RIGHT, padx=5,
        )
        ttk.Button(toolbar, text="전체 삭제", command=self._clear_all).pack(
            side=tk.RIGHT, padx=5,
        )
        ttk.Button(toolbar, text="그래프 정보 내보내기", command=self._export_info).pack(
            side=tk.RIGHT, padx=5,
        )
        ttk.Button(toolbar, text="🔬 TDA Distance", command=self._open_power_grid_tda).pack(
            side=tk.RIGHT, padx=5,
        )
        ttk.Button(toolbar, text="📊 TDA 탐색기", command=self._tda_explorer).pack(
            side=tk.RIGHT, padx=5,
        )
        ttk.Button(toolbar, text="⚠ 취약점 분석", command=self._vulnerability_analysis).pack(
            side=tk.RIGHT, padx=5,
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

        ttk.Button(
            win,
            text="5-Bus 테스트",
            command=lambda: load_test_grid("5-Bus", get_test_grid_5bus),
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
        """Open the TDA Explorer using the extracted TdaExplorerWindow."""
        if len(self.nodes) == 0:
            messagebox.showinfo("TDA 탐색기", "그래프에 노드가 없습니다.\n먼저 노드를 추가하세요!")
            return

        explorer = TdaExplorerWindow(
            self.root, self.nodes, self.edges,
            on_ask_ai=lambda parent_win: self._ask_ai_tda(parent_win),
        )
        explorer.open()

    # ─── AI Analysis via OpenRouter ──────────────────────────────

    def _ask_ai_tda(self, parent_win):
        """Send graph diagram + TDA data to DeepSeek (via OpenRouter) for interpretation."""
        analyzer = AiAnalyzer(parent_win, api_key=self._api_key)
        analyzer.ask(self.canvas, self.nodes, self.edges)
        # Store the api_key if it was set during the prompt
        if analyzer._api_key:
            self._api_key = analyzer._api_key

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
                "경고", "취약점 분석을 위해 최소 2개 이상의 노드가 필요합니다.",
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
                dist_matrix, vr, bus_labels, top_k=10,
            )
        except Exception as e:
            messagebox.showerror("오류", f"취약점 점수 계산 중 오류: {e}")
            return

        # ── 4. Same-score clustering check ────────────────────────────
        # Detect if too many nodes share the same score → algorithm weakness
        unique_scores, counts = np.unique(
            np.round(scores, decimals=4), return_counts=True
        )
        max_same_score_count = int(np.max(counts)) if len(counts) > 0 else 0
        same_score_ratio = max_same_score_count / max(len(scores), 1)
        algorithm_weak = same_score_ratio > 0.5 and len(unique_scores) < len(scores) * 0.3

        # ── 5. Update summary with enriched info ──────────────────────
        b0, b1 = vr.betti_numbers(float(vr.max_distance / 2))
        n_vuln_high = int(np.sum(scores > 0.7))
        n_vuln_medium = int(np.sum((scores > 0.4) & (scores <= 0.7)))
        summary["overall_beta0"] = b0
        summary["overall_beta1"] = b1
        summary["n_vulnerable_high"] = n_vuln_high
        summary["n_vulnerable_medium"] = n_vuln_medium
        summary["top_node_idx"] = int(np.argmax(scores))
        summary["top_node_label"] = bus_labels[int(np.argmax(scores))]
        summary["top_node_score"] = float(np.max(scores))
        summary["algorithm_weak"] = algorithm_weak
        summary["same_score_ratio"] = float(same_score_ratio)

        # ── 6. Warn if algorithm is too weak ──────────────────────────
        if algorithm_weak:
            messagebox.showwarning(
                "⚠ 취약점 알고리즘 강화 필요",
                f"동일한 점수를 가진 노드가 너무 많습니다 "
                f"(최대 {max_same_score_count}개 노드가 동일 점수, "
                f"비율: {same_score_ratio * 100:.1f}%).\n\n"
                f"현재 취약점 알고리즘의 변별력이 충분하지 않습니다.\n"
                f"더 정교한 거리 함수나 새로운 취약점 지표가 필요합니다.",
            )

        # ── 7. Color nodes on canvas ────────────────────────────────
        self._color_nodes_by_score(scores)

        # ── 8. Show results window ─────────────────────────────────
        grid_name = "수동 그래프"
        if self._power_grid_data:
            grid_name = self._power_grid_data.get("name", "전력망")

        show_vulnerability_window(
            parent=self.root,
            scores=scores,
            summary=summary,
            vr=vr,
            dist_matrix=dist_matrix,
            bus_labels=bus_labels,
            power_grid_name=grid_name,
            reset_colors_callback=self._reset_node_colors,
        )

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

            PTDF = compute_ptdf(n, bus_pairs, susceptances, slack)
            return compute_ptdf_vector_distance(PTDF)
        except Exception as e:
            messagebox.showwarning(
                "전기거리 실패",
                f"전기거리 계산 실패 ({e}), 좌표 거리로 대체합니다.",
            )
            return self._build_euclidean_distance_matrix()

    def _color_nodes_by_score(self, scores: np.ndarray):
        """Color nodes on canvas based on vulnerability scores.

        Coloring strategy:
          - ★ Top 1 highest-scoring node → magenta (#FF00FF) for maximum visibility
          - Vulnerable (top 20% or score > 0.7) → red gradient (#FF4444 ~ #FFAA00)
          - Safe → green gradient (#44BB44 ~ #88FF88)
          - If more than 20% of nodes exceed the default threshold (0.7),
            only the top 20% are marked as vulnerable.
        """
        n = len(scores)
        if n == 0 or not self.nodes:
            return

        # ── 1. Identify the single most vulnerable node ──────────
        top_idx = int(np.argmax(scores))

        # ── 2. Determine vulnerability threshold ─────────────────
        # Default high-risk threshold from the listbox logic (score > 0.7)
        vuln_threshold = 0.7
        n_vuln_candidates = int(np.sum(scores > vuln_threshold))
        vuln_ratio = n_vuln_candidates / n if n > 0 else 0

        if vuln_ratio > 0.2:
            # More than 20% are "vulnerable" → cap at top 20%
            sorted_idx = np.argsort(scores)[::-1]
            top_20pct_count = max(1, int(np.ceil(n * 0.2)))
            cutoff_score = scores[sorted_idx[top_20pct_count - 1]]
            is_vulnerable = scores >= cutoff_score
        else:
            is_vulnerable = scores > vuln_threshold

        # ── 3. Color each node ───────────────────────────────────
        for i, node in enumerate(self.nodes):
            if i >= n:
                continue

            if i == top_idx:
                # ★ Single most vulnerable node → magenta
                node.set_color("#FF00FF")
            elif is_vulnerable[i]:
                # Vulnerable → red gradient
                t = min(1.0, scores[i])
                r = int(255)
                g = int(200 * (1 - t))
                b = int(100 * (1 - t))
                color = f"#{r:02x}{max(g, 0):02x}{max(b, 0):02x}"
                node.set_color(color)
            else:
                # Safe → green gradient
                t = max(0.0, scores[i])
                g_base = 0xBB
                r = int(120 * t)
                g = int(g_base + (255 - g_base) * (1 - t))
                b = int(80 * t)
                color = f"#{min(r, 255):02x}{min(g, 255):02x}{min(b, 255):02x}"
                node.set_color(color)

    def _reset_node_colors(self):
        """Reset all node colors to default (light blue)."""
        for node in self.nodes:
            node.set_color(Node.COLOR_NORMAL)


def main():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")
    app = GraphEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
