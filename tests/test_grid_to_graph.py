"""
Tests for grid_to_graph.py — GridGraphConverter.

Covers:
  - Initialization and bus index building
  - Properties (n_bus, n_line, bus_pairs, susceptances, bus_positions, node_labels)
  - compute_layout (auto-layout for zero coordinates, scaling for meaningful coords)
  - _scale_positions
  - add_to_editor (mock-based)
  - get_electrical_data
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import numpy as np
import pytest

from integration.grid_to_graph import GridGraphConverter


# ─── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def simple_grid():
    """3-bus triangle grid with meaningful coordinates."""
    return {
        "name": "test",
        "buses": [
            {"id": 0, "name": "Bus0", "x": 0.0, "y": 0.0, "v_nom": 330.0},
            {"id": 1, "name": "Bus1", "x": 1.0, "y": 0.0, "v_nom": 330.0},
            {"id": 2, "name": "Bus2", "x": 0.5, "y": 0.866, "v_nom": 330.0},
        ],
        "lines": [
            {"id": 0, "name": "L0", "from_bus": 0, "to_bus": 1, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 1, "name": "L1", "from_bus": 1, "to_bus": 2, "x": 0.2, "r": 0.02, "rate": 100.0},
            {"id": 2, "name": "L2", "from_bus": 0, "to_bus": 2, "x": 0.15, "r": 0.015, "rate": 100.0},
        ],
        "generators": [{"bus": 0, "p_mw": 100.0, "name": "G0"}],
        "loads": [{"bus": 2, "p_mw": 100.0, "name": "Ld0"}],
    }


@pytest.fixture
def grid_zero_coords():
    """3-bus grid with all-zero coordinates (triggers auto-layout)."""
    return {
        "name": "test_zero",
        "buses": [
            {"id": 10, "name": "Alpha", "x": 0.0, "y": 0.0, "v_nom": 330.0},
            {"id": 20, "name": "Beta", "x": 0.0, "y": 0.0, "v_nom": 330.0},
            {"id": 30, "name": "Gamma", "x": 0.0, "y": 0.0, "v_nom": 330.0},
        ],
        "lines": [
            {"id": 0, "name": "L0", "from_bus": 10, "to_bus": 20, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 1, "name": "L1", "from_bus": 20, "to_bus": 30, "x": 0.2, "r": 0.02, "rate": 100.0},
            {"id": 2, "name": "L2", "from_bus": 10, "to_bus": 30, "x": 0.15, "r": 0.015, "rate": 100.0},
        ],
        "generators": [],
        "loads": [],
    }


@pytest.fixture
def grid_single_bus():
    """Single bus grid."""
    return {
        "name": "single",
        "buses": [
            {"id": 0, "name": "Only", "x": 0.0, "y": 0.0, "v_nom": 330.0},
        ],
        "lines": [],
        "generators": [],
        "loads": [],
    }


@pytest.fixture
def grid_two_components():
    """Two disconnected components (triangles) with zero coordinates."""
    return {
        "name": "two_comp",
        "buses": [
            {"id": 0, "name": "A0", "x": 0.0, "y": 0.0},
            {"id": 1, "name": "A1", "x": 0.0, "y": 0.0},
            {"id": 2, "name": "A2", "x": 0.0, "y": 0.0},
            {"id": 3, "name": "B0", "x": 0.0, "y": 0.0},
            {"id": 4, "name": "B1", "x": 0.0, "y": 0.0},
            {"id": 5, "name": "B2", "x": 0.0, "y": 0.0},
        ],
        "lines": [
            {"id": 0, "from_bus": 0, "to_bus": 1, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 1, "from_bus": 1, "to_bus": 2, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 2, "from_bus": 0, "to_bus": 2, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 3, "from_bus": 3, "to_bus": 4, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 4, "from_bus": 4, "to_bus": 5, "x": 0.1, "r": 0.01, "rate": 100.0},
            {"id": 5, "from_bus": 3, "to_bus": 5, "x": 0.1, "r": 0.01, "rate": 100.0},
        ],
        "generators": [],
        "loads": [],
    }


# ─── Initialization Tests ───────────────────────────────────

class TestInit:
    """Test GridGraphConverter initialization."""

    def test_creates_bus_index(self, simple_grid):
        """Bus index should map bus IDs to sequential indices."""
        conv = GridGraphConverter(simple_grid)
        assert conv._bus_to_idx == {0: 0, 1: 1, 2: 2}

    def test_non_sequential_ids(self):
        """Bus IDs should be mapped correctly even if non-sequential."""
        grid = {
            "buses": [
                {"id": 10, "name": "A", "x": 0, "y": 0},
                {"id": 20, "name": "B", "x": 0, "y": 0},
            ],
            "lines": [],
            "generators": [],
            "loads": [],
        }
        conv = GridGraphConverter(grid)
        assert conv._bus_to_idx == {10: 0, 20: 1}

    def test_empty_buses(self):
        """Empty grid should not crash."""
        grid = {"buses": [], "lines": [], "generators": [], "loads": []}
        conv = GridGraphConverter(grid)
        assert conv.n_bus == 0
        assert conv.n_line == 0
        assert conv.bus_pairs == []
        assert conv.susceptances == []
        assert conv.bus_positions == []


# ─── Property Tests ─────────────────────────────────────────

class TestProperties:
    """Test GridGraphConverter properties."""

    def test_n_bus(self, simple_grid):
        assert GridGraphConverter(simple_grid).n_bus == 3

    def test_n_line(self, simple_grid):
        assert GridGraphConverter(simple_grid).n_line == 3

    def test_n_bus_zero(self):
        conv = GridGraphConverter({"buses": [], "lines": [], "generators": [], "loads": []})
        assert conv.n_bus == 0

    def test_bus_pairs(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        assert conv.bus_pairs == [(0, 1), (1, 2), (0, 2)]

    def test_bus_pairs_non_sequential_ids(self):
        grid = {
            "buses": [{"id": 10}, {"id": 20}, {"id": 30}],
            "lines": [
                {"from_bus": 10, "to_bus": 20, "x": 0.1, "r": 0.01, "rate": 100.0},
                {"from_bus": 20, "to_bus": 30, "x": 0.1, "r": 0.01, "rate": 100.0},
            ],
            "generators": [],
            "loads": [],
        }
        conv = GridGraphConverter(grid)
        assert conv.bus_pairs == [(0, 1), (1, 2)]

    def test_susceptances(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        expected = [1.0 / 0.1, 1.0 / 0.2, 1.0 / 0.15]
        np.testing.assert_array_almost_equal(conv.susceptances, expected)

    def test_susceptances_min_clamp(self):
        """Zero or near-zero x should be clamped to 1e-6."""
        grid = {
            "buses": [{"id": 0}, {"id": 1}],
            "lines": [{"from_bus": 0, "to_bus": 1, "x": 0.0, "r": 0.0, "rate": 100.0}],
            "generators": [],
            "loads": [],
        }
        conv = GridGraphConverter(grid)
        assert conv.susceptances == [1.0 / 1e-6]

    def test_bus_positions(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        expected = [(0.0, 0.0), (1.0, 0.0), (0.5, 0.866)]
        for (px, py), (ex, ey) in zip(conv.bus_positions, expected):
            assert px == pytest.approx(ex, abs=1e-3)
            assert py == pytest.approx(ey, abs=1e-3)

    def test_bus_positions_default_zero(self):
        """Missing x/y should default to 0.0."""
        grid = {
            "buses": [{"id": 0, "name": "A"}, {"id": 1, "name": "B"}],
            "lines": [],
            "generators": [],
            "loads": [],
        }
        conv = GridGraphConverter(grid)
        assert conv.bus_positions == [(0.0, 0.0), (0.0, 0.0)]

    def test_node_labels(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        assert conv.node_labels == ["Bus0", "Bus1", "Bus2"]

    def test_node_labels_default(self):
        """Missing name should generate default label."""
        grid = {
            "buses": [{"id": 5}, {"id": 10}],
            "lines": [],
            "generators": [],
            "loads": [],
        }
        conv = GridGraphConverter(grid)
        assert conv.node_labels == ["B5", "B10"]


# ─── compute_layout Tests ───────────────────────────────────

class TestComputeLayout:
    """Test compute_layout method."""

    def test_meaningful_coordinates_scaled(self, simple_grid):
        """Grid with meaningful coordinates should be scaled, not auto-laid-out."""
        conv = GridGraphConverter(simple_grid)
        positions = conv.compute_layout(scale_x=600, scale_y=400)
        assert len(positions) == 3
        # All positions should be within canvas bounds
        for x, y in positions:
            assert 0 <= x <= 600
            assert 0 <= y <= 400

    def test_zero_coordinates_auto_layout(self, grid_zero_coords):
        """All-zero coordinates should trigger circular auto-layout."""
        conv = GridGraphConverter(grid_zero_coords)
        positions = conv.compute_layout(scale_x=600, scale_y=400)
        assert len(positions) == 3
        # All positions should be within canvas bounds
        for x, y in positions:
            assert 0 <= x <= 600
            assert 0 <= y <= 400

    def test_auto_layout_circular_arrangement(self, grid_zero_coords):
        """Auto-layout should place buses in a circular pattern."""
        conv = GridGraphConverter(grid_zero_coords)
        positions = conv.compute_layout(scale_x=600, scale_y=400)
        # For 3 buses in a circle, positions should be roughly equidistant
        # Compute pairwise distances
        dists = []
        for i in range(3):
            for j in range(i + 1, 3):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dists.append(math.sqrt(dx * dx + dy * dy))
        # All distances should be similar (within 10%)
        mean_d = sum(dists) / len(dists)
        for d in dists:
            assert abs(d - mean_d) / mean_d < 0.15

    def test_single_bus_layout(self, grid_single_bus):
        """Single bus should be placed at center."""
        conv = GridGraphConverter(grid_single_bus)
        positions = conv.compute_layout(scale_x=600, scale_y=400)
        assert len(positions) == 1
        # Single bus should be at center of canvas
        assert positions[0][0] == pytest.approx(300, abs=50)
        assert positions[0][1] == pytest.approx(40, abs=50)

    def test_two_components_layout(self, grid_two_components):
            """Two disconnected components should both be placed.
            Auto-layout may place components outside strict canvas bounds."""
            conv = GridGraphConverter(grid_two_components)
            positions = conv.compute_layout(scale_x=600, scale_y=400)
            assert len(positions) == 6
            # All positions should be non-negative and finite
            for x, y in positions:
                assert x >= 0
                assert y >= 0
                assert math.isfinite(x)
                assert math.isfinite(y)


# ─── _scale_positions Tests ─────────────────────────────────

class TestScalePositions:
    """Test the static _scale_positions method."""

    def test_simple_scale(self):
        """Positions should be scaled to fit canvas."""
        positions = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        scaled = GridGraphConverter._scale_positions(positions, 600, 400, 50)
        assert len(scaled) == 3
        for x, y in scaled:
            assert 50 <= x <= 550  # 600 - 2*50
            assert 50 <= y <= 350  # 400 - 2*50

    def test_single_point_scale(self):
        """Single point should be centered."""
        positions = [(0.0, 0.0)]
        scaled = GridGraphConverter._scale_positions(positions, 600, 400, 50)
        assert len(scaled) == 1
        # Single point at (0,0) -> scaled to (margin, margin) = (50, 50)
        assert scaled[0] == (50.0, 50.0)

    def test_all_same_coordinate(self):
        """All same coordinates should not crash and return margin positions."""
        positions = [(5.0, 5.0), (5.0, 5.0)]
        scaled = GridGraphConverter._scale_positions(positions, 600, 400, 50)
        assert len(scaled) == 2
        # range_x = 1 (clamped), range_y = 1 (clamped)
        # Both points map to (margin, margin)
        assert scaled[0] == (50.0, 50.0)
        assert scaled[1] == (50.0, 50.0)

    def test_scale_factor_preserves_aspect_ratio(self):
        """Proportional distances should be preserved under scaling."""
        positions = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        scaled = GridGraphConverter._scale_positions(positions, 600, 400, 50)
        # Distance between first two points in original: 1.0
        # Distance between first two points in scaled: 500.0 (600 - 2*50)
        dx = scaled[1][0] - scaled[0][0]
        assert dx == pytest.approx(500.0, abs=1.0)


# ─── add_to_editor Tests ────────────────────────────────────

class TestAddToEditor:
    """Test add_to_editor method with a mock editor."""

    def test_adds_nodes_and_edges(self, simple_grid):
        """Should call add_node and add_edge on the editor."""
        conv = GridGraphConverter(simple_grid)

        # Mock editor
        class MockEditor:
            def __init__(self):
                self.nodes = []
                self.edges = []
                self.cleared = False

            def _clear_all(self):
                self.cleared = True
                self.nodes = []
                self.edges = []

            def add_node(self, x, y, label=None):
                node = {"x": x, "y": y, "label": label}
                self.nodes.append(node)
                return node

            def add_edge(self, source, target, label=None):
                edge = {"source": source, "target": target, "label": label}
                self.edges.append(edge)
                return edge

        editor = MockEditor()
        conv.add_to_editor(editor)

        assert editor.cleared
        assert len(editor.nodes) == 3
        assert len(editor.edges) == 3

        # Check node labels
        labels = [n["label"] for n in editor.nodes]
        assert "Bus0" in labels
        assert "Bus1" in labels
        assert "Bus2" in labels

        # Check edge labels
        edge_labels = [e["label"] for e in editor.edges]
        assert "L0" in edge_labels
        assert "L1" in edge_labels
        assert "L2" in edge_labels

    def test_idempotent(self, simple_grid):
        """Second call to add_to_editor should be no-op (early return)."""
        conv = GridGraphConverter(simple_grid)

        call_count = {"clear": 0, "add_node": 0, "add_edge": 0}

        class MockEditor:
            def _clear_all(self):
                call_count["clear"] += 1

            def add_node(self, x, y, label=None):
                call_count["add_node"] += 1
                return {"x": x, "y": y, "label": label}

            def add_edge(self, source, target, label=None):
                call_count["add_edge"] += 1
                return {"source": source, "target": target, "label": label}

        editor = MockEditor()
        conv.add_to_editor(editor)
        conv.add_to_editor(editor)  # second call

        # Only first call should have effect
        assert call_count["clear"] == 1
        assert call_count["add_node"] == 3
        assert call_count["add_edge"] == 3

    def test_use_geo_layout(self, simple_grid):
        """use_geo_layout=True should use scaling, not auto-layout."""
        conv = GridGraphConverter(simple_grid)

        class MockEditor:
            def __init__(self):
                self.nodes = []

            def _clear_all(self):
                self.nodes = []

            def add_node(self, x, y, label=None):
                node = {"x": x, "y": y, "label": label}
                self.nodes.append(node)
                return node

            def add_edge(self, source, target, label=None):
                return {"source": source, "target": target, "label": label}

        editor = MockEditor()
        conv.add_to_editor(editor, use_geo_layout=True)
        assert len(editor.nodes) == 3
        # With geo layout and meaningful coords, positions should be scaled
        # Bus0 (0,0) -> (50, 50), Bus1 (1,0) -> (550, 50)
        assert editor.nodes[0]["x"] == pytest.approx(50, abs=1)
        assert editor.nodes[1]["x"] == pytest.approx(550, abs=1)

    def test_empty_grid(self):
        """Empty grid should clear editor and add nothing."""
        conv = GridGraphConverter({"buses": [], "lines": [], "generators": [], "loads": []})

        class MockEditor:
            def __init__(self):
                self.cleared = False
                self.add_node_called = False
                self.add_edge_called = False

            def _clear_all(self):
                self.cleared = True

            def add_node(self, x, y, label=None):
                self.add_node_called = True
                return {}

            def add_edge(self, source, target, label=None):
                self.add_edge_called = True
                return {}

        editor = MockEditor()
        conv.add_to_editor(editor)
        assert editor.cleared
        assert not editor.add_node_called
        assert not editor.add_edge_called


# ─── get_electrical_data Tests ──────────────────────────────

class TestGetElectricalData:
    """Test get_electrical_data method."""

    def test_returns_dict(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        data = conv.get_electrical_data()
        assert isinstance(data, dict)

    def test_keys_present(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        data = conv.get_electrical_data()
        assert "n_bus" in data
        assert "n_line" in data
        assert "bus_pairs" in data
        assert "susceptances" in data
        assert "bus_positions" in data
        assert "bus_labels" in data
        assert "grid_data" in data

    def test_values_correct(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        data = conv.get_electrical_data()
        assert data["n_bus"] == 3
        assert data["n_line"] == 3
        assert data["bus_pairs"] == [(0, 1), (1, 2), (0, 2)]
        assert data["bus_labels"] == ["Bus0", "Bus1", "Bus2"]
        assert data["grid_data"] is simple_grid

    def test_susceptances_in_data(self, simple_grid):
        conv = GridGraphConverter(simple_grid)
        data = conv.get_electrical_data()
        expected = [1.0 / 0.1, 1.0 / 0.2, 1.0 / 0.15]
        np.testing.assert_array_almost_equal(data["susceptances"], expected)

