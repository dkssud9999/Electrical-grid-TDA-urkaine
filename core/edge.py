"""Directed edge between two Node objects with canvas rendering."""

from __future__ import annotations

import tkinter as tk

from core.node import Node


class Edge:
    """Represents a directed edge between two Node objects."""

    COLOR_NORMAL = "#888888"
    COLOR_HOVER = "#AAAAAA"
    ARROW_SIZE = 10
    WIDTH = 2

    def __init__(
        self,
        canvas: tk.Canvas,
        source: Node,
        target: Node,
        label: str | None = None,
    ):
        self.canvas = canvas
        self.source = source
        self.target = target
        self.label = label or ""
        self.color = Edge.COLOR_NORMAL

        self._line_id: int | None = None
        self._arrow_id: int | None = None
        self._label_id: int | None = None
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
            sx, sy, tx, ty, fill=self.color, width=Edge.WIDTH, tags=("edge",),
        )

        # Arrowhead
        ax = self.ARROW_SIZE
        p1_x = tx + ux * ax - uy * ax * 0.5
        p1_y = ty + uy * ax + ux * ax * 0.5
        p2_x = tx + ux * ax + uy * ax * 0.5
        p2_y = ty + uy * ax - ux * ax * 0.5
        self._arrow_id = self.canvas.create_polygon(
            tx, ty, p1_x, p1_y, p2_x, p2_y,
            fill=self.color, outline=self.color, tags=("edge_arrow",),
        )

        # Label in the middle of the edge
        if self.label:
            mx, my = (sx + tx) / 2, (sy + ty) / 2
            self._label_id = self.canvas.create_text(
                mx, my, text=self.label,
                font=("Helvetica", 9), fill="#CCCCCC", tags=("edge_label",),
            )

    def redraw(self):
        """Redraw the edge after node movement."""
        self.canvas.delete(self._line_id)
        self.canvas.delete(self._arrow_id)
        if self._label_id:
            self.canvas.delete(self._label_id)
        self._draw()

    def set_color(self, color: str):
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

    def __repr__(self) -> str:
        return f"Edge({self.source} -> {self.target})"

