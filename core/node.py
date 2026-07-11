"""Graph vertex class with canvas rendering and hit testing."""

from __future__ import annotations

import tkinter as tk


class Node:
    """Represents a single node in the graph."""

    RADIUS = 20
    COLOR_NORMAL = "#4A90D9"
    COLOR_HOVER = "#6DB3F8"
    COLOR_SELECTED = "#FF6B6B"
    FONT = ("Helvetica", 10, "bold")

    def __init__(self, canvas: tk.Canvas, x: float, y: float, label: str | None = None):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.label = label or ""
        self.edges: list = []  # list of Edge objects connected to this node
        self.radius = Node.RADIUS
        self.color = Node.COLOR_NORMAL

        self._id: int | None = None  # canvas oval id
        self._text_id: int | None = None  # canvas text id
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

    def update_position(self, x: float, y: float):
        """Move the node to a new position and redraw connected edges."""
        self.x = x
        self.y = y
        self.canvas.coords(
            self._id, x - self.radius, y - self.radius, x + self.radius, y + self.radius,
        )
        self.canvas.coords(self._text_id, x, y)
        for edge in self.edges:
            edge.redraw()

    def set_color(self, color: str):
        """Change the fill color of the node."""
        self.color = color
        self.canvas.itemconfig(self._id, fill=color)

    def contains_point(self, x: float, y: float) -> bool:
        """Check if (x, y) is inside this node."""
        dx = self.x - x
        dy = self.y - y
        return dx * dx + dy * dy <= self.radius * self.radius

    def delete(self):
        """Remove the node's canvas items."""
        self.canvas.delete(self._id)
        self.canvas.delete(self._text_id)

    def __repr__(self) -> str:
        return f"Node({self.label or '?'}, {self.x}, {self.y})"

