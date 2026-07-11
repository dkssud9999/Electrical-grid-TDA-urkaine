"""
Convert a power grid data dict (from power_grid.importer) into
the graph editor's internal node/edge representation.

Also stores electrical parameters needed for PTDF computation.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


class GridGraphConverter:
    """
    Converts a power grid (dict format) into graph editor nodes/edges
    while preserving electrical parameters.

    Usage:
        conv = GridGraphConverter(grid_data)
        conv.add_to_editor(graph_editor)   # adds nodes + edges

        conv.bus_pairs       # list of (from_idx, to_idx)
        conv.susceptances    # list of line susceptances
        conv.bus_positions   # list of (x, y) for layout
    """

    def __init__(self, grid_data: dict):
        self.grid = grid_data
        self.buses: list[dict] = grid_data.get("buses", [])
        self.lines: list[dict] = grid_data.get("lines", [])
        self.generators: list[dict] = grid_data.get("generators", [])
        self.loads: list[dict] = grid_data.get("loads", [])

        # Generated after import
        self._node_map: dict[int, Any] = {}  # bus_id → Node object
        self._edge_map: dict[int, Any] = {}  # line_id → Edge object
        self._bus_to_idx: dict[int, int] = {}  # bus_id → sequential index

        # Pre-compute electrical data
        self._build_bus_index()

    def _build_bus_index(self):
        """Map bus IDs to sequential indices 0..n-1."""
        for i, bus in enumerate(self.buses):
            self._bus_to_idx[bus["id"]] = i

    @property
    def n_bus(self) -> int:
        return len(self.buses)

    @property
    def n_line(self) -> int:
        return len(self.lines)

    @property
    def bus_pairs(self) -> list[tuple[int, int]]:
        """List of (from_bus_idx, to_bus_idx) for each line."""
        pairs = []
        for line in self.lines:
            f = self._bus_to_idx.get(line["from_bus"], 0)
            t = self._bus_to_idx.get(line["to_bus"], 0)
            pairs.append((f, t))
        return pairs

    @property
    def susceptances(self) -> list[float]:
        """Line susceptances b = 1/x (per unit)."""
        return [1.0 / max(line["x"], 1e-6) for line in self.lines]

    @property
    def bus_positions(self) -> list[tuple[float, float]]:
        """Bus (x, y) positions for layout. Auto-layout if missing."""
        positions = []
        for bus in self.buses:
            x = bus.get("x", 0.0)
            y = bus.get("y", 0.0)
            positions.append((x, y))
        return positions

    def compute_layout(self, scale_x: float = 600, scale_y: float = 400,
                       margin: float = 50) -> list[tuple[float, float]]:
        """
        Auto-layout buses if coordinates are all zero.

        Uses a simple spring-like layout based on line connections.
        """
        raw = self.bus_positions
        xs = [p[0] for p in raw]
        ys = [p[1] for p in raw]

        if max(xs) - min(xs) > 1 or max(ys) - min(ys) > 1:
            # Has meaningful coordinates — just scale them
            return self._scale_positions(raw, scale_x, scale_y, margin)

        # Auto-layout: place connected buses in a circle per component
        n = self.n_bus
        adj: list[list[int]] = [[] for _ in range(n)]
        for f, t in self.bus_pairs:
            if f < n and t < n:
                adj[f].append(t)
                adj[t].append(f)

        # Find connected components
        visited = [False] * n
        components: list[list[int]] = []
        for i in range(n):
            if not visited[i]:
                comp = []
                stack = [i]
                while stack:
                    v = stack.pop()
                    if not visited[v]:
                        visited[v] = True
                        comp.append(v)
                        stack.extend(adj[v])
                components.append(comp)

        positions = [None] * n
        y_offset = margin
        for comp in components:
            c = len(comp)
            if c == 1:
                positions[comp[0]] = (scale_x / 2, y_offset + 40)
                y_offset += 80
            else:
                r = min(scale_x, scale_y) / 4
                cx, cy = scale_x / 2, y_offset + r + margin
                for k, idx in enumerate(comp):
                    angle = 2 * math.pi * k / c - math.pi / 2
                    px = cx + r * math.cos(angle)
                    py = cy + r * math.sin(angle)
                    positions[idx] = (px, py)
                y_offset += 2 * r + 2 * margin + 40

        return positions  # type: ignore

    @staticmethod
    def _scale_positions(positions: list[tuple[float, float]],
                         scale_x: float, scale_y: float,
                         margin: float) -> list[tuple[float, float]]:
        """Scale raw coordinates to fit canvas."""
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        range_x = max_x - min_x if max_x > min_x else 1
        range_y = max_y - min_y if max_y > min_y else 1
        scaled = []
        for x, y in positions:
            sx = margin + ((x - min_x) / range_x) * (scale_x - 2 * margin)
            sy = margin + ((y - min_y) / range_y) * (scale_y - 2 * margin)
            scaled.append((sx, sy))
        return scaled

    def add_to_editor(self, editor, layout_scale: tuple[float, float] = (600, 400),
                      use_geo_layout: bool = False):
        """
        Add all buses and lines to a GraphEditor instance.

        Parameters
        ----------
        editor : GraphEditor
        layout_scale : (width, height)
        use_geo_layout : bool
            If True, use geographic coordinates from the grid data.
            If False, auto-layout.
        """
        # Skip if already imported
        if self._node_map:
            return

        # Clear existing graph
        editor._clear_all()

        # Determine positions
        if use_geo_layout:
            positions = self._scale_positions(
                self.bus_positions, layout_scale[0], layout_scale[1], 50
            )
        else:
            positions = self.compute_layout(layout_scale[0], layout_scale[1])

        # Create nodes
        for i, bus in enumerate(self.buses):
            x, y = positions[i] if i < len(positions) else (300, 300)
            label = bus.get("name", f"B{bus['id']}")
            node = editor.add_node(x, y, label=label)
            self._node_map[bus["id"]] = node

        # Create edges
        for line in self.lines:
            src = self._node_map.get(line["from_bus"])
            dst = self._node_map.get(line["to_bus"])
            if src and dst:
                label = line.get("name", f"L{line['id']}")
                edge = editor.add_edge(src, dst, label=label)
                self._edge_map[line["id"]] = edge

    @property
    def node_labels(self) -> list[str]:
        """Get node labels in sequential order."""
        labels = []
        for bus in self.buses:
            labels.append(bus.get("name", f"B{bus['id']}"))
        return labels

    def get_electrical_data(self) -> dict:
        """Return PTDF-ready electrical data."""
        return {
            "n_bus": self.n_bus,
            "n_line": self.n_line,
            "bus_pairs": self.bus_pairs,
            "susceptances": self.susceptances,
            "bus_positions": self.bus_positions,
            "bus_labels": self.node_labels,
        }

