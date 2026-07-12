"""Tests for ukraine_loader.py — Ukraine grid data validation.

Verifies the structural integrity of built-in Ukraine grid models:
  - get_ukraine_330kv_grid()  (18-bus)
  - get_large_ukraine_grid()  (28-bus)
  - get_sample_ukraine_grid() (deprecated wrapper)

Checks cover:
  - Dict structure and required keys
  - Bus/line/gen/load counts and IDs
  - Reference integrity (line → bus, gen → bus, load → bus)
  - No duplicate IDs
  - Required fields present
  - Voltage levels
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from power_grid.ukraine_loader import (
    get_ukraine_330kv_grid,
    get_large_ukraine_grid,
    get_sample_ukraine_grid,
)

# ─── Helpers ────────────────────────────────────────────────

REQUIRED_BUS_FIELDS = {"id", "name", "x", "y", "v_nom"}
REQUIRED_LINE_FIELDS = {"id", "name", "from_bus", "to_bus", "x", "r", "rate"}
REQUIRED_GEN_FIELDS = {"bus", "p_mw", "name"}
REQUIRED_LOAD_FIELDS = {"bus", "p_mw", "name"}
REQUIRED_TOP_KEYS = {"name", "buses", "lines", "generators", "loads", "base_mva"}


def check_grid_structure(grid: dict) -> None:
    """Assert basic structural integrity of a grid dict."""
    assert isinstance(grid, dict)
    for key in REQUIRED_TOP_KEYS:
        assert key in grid, f"Missing top-level key: {key}"
    assert isinstance(grid["buses"], list)
    assert isinstance(grid["lines"], list)
    assert isinstance(grid["generators"], list)
    assert isinstance(grid["loads"], list)
    assert isinstance(grid["base_mva"], (int, float))


def check_bus_ids_unique(buses: list[dict]) -> None:
    """Assert all bus IDs are unique."""
    ids = [b["id"] for b in buses]
    assert len(ids) == len(set(ids)), "Duplicate bus IDs found"


def check_line_ids_unique(lines: list[dict]) -> None:
    """Assert all line IDs are unique."""
    ids = [ln["id"] for ln in lines]
    assert len(ids) == len(set(ids)), "Duplicate line IDs found"


def check_bus_references_valid(buses: list[dict], lines: list[dict],
                               generators: list[dict], loads: list[dict]) -> None:
    """Assert all from_bus/to_bus/bus references point to valid bus IDs."""
    bus_ids = {b["id"] for b in buses}
    for line in lines:
        assert line["from_bus"] in bus_ids, \
            f"Line {line['id']}: from_bus {line['from_bus']} not in buses"
        assert line["to_bus"] in bus_ids, \
            f"Line {line['id']}: to_bus {line['to_bus']} not in buses"
    for gen in generators:
        assert gen["bus"] in bus_ids, \
            f"Generator '{gen['name']}': bus {gen['bus']} not in buses"
    for load in loads:
        assert load["bus"] in bus_ids, \
            f"Load '{load['name']}': bus {load['bus']} not in buses"


# ─── 18-Bus Grid Tests ─────────────────────────────────────

class TestUkraine330kVGrid:
    """Test get_ukraine_330kv_grid() structural integrity."""

    @pytest.fixture
    def grid(self):
        return get_ukraine_330kv_grid()

    def test_returns_dict_with_required_keys(self, grid):
        """Grid dict has all required top-level keys."""
        check_grid_structure(grid)

    def test_name(self, grid):
        """Grid name should contain '330' and 'Ukraine'."""
        assert "330" in grid["name"]
        assert "Ukraine" in grid["name"]

    def test_bus_count(self, grid):
        """Should have exactly 18 buses."""
        assert len(grid["buses"]) == 18

    def test_line_count(self, grid):
        """Should have exactly 25 lines."""
        assert len(grid["lines"]) == 25

    def test_generator_count(self, grid):
        """Should have exactly 8 generators."""
        assert len(grid["generators"]) == 8

    def test_load_count(self, grid):
        """Should have exactly 8 loads."""
        assert len(grid["loads"]) == 8

    def test_base_mva(self, grid):
        """base_mva should be 100.0."""
        assert grid["base_mva"] == 100.0

    def test_bus_ids_sequential(self, grid):
        """Bus IDs should be 0 through 17."""
        bus_ids = sorted(b["id"] for b in grid["buses"])
        assert bus_ids == list(range(18))

    def test_line_ids_sequential(self, grid):
        """Line IDs should be 0 through 24."""
        line_ids = sorted(ln["id"] for ln in grid["lines"])
        assert line_ids == list(range(25))

    def test_bus_ids_unique(self, grid):
        """All bus IDs are unique."""
        check_bus_ids_unique(grid["buses"])

    def test_line_ids_unique(self, grid):
        """All line IDs are unique."""
        check_line_ids_unique(grid["lines"])

    def test_buses_have_required_fields(self, grid):
        """Every bus has all required fields."""
        for bus in grid["buses"]:
            missing = REQUIRED_BUS_FIELDS - set(bus.keys())
            assert not missing, f"Bus {bus.get('id', '?')} missing fields: {missing}"

    def test_lines_have_required_fields(self, grid):
        """Every line has all required fields."""
        for line_ in grid["lines"]:
            missing = REQUIRED_LINE_FIELDS - set(line_.keys())
            assert not missing, f"Line {line_.get('id', '?')} missing fields: {missing}"

    def test_generators_have_required_fields(self, grid):
        """Every generator has all required fields."""
        for gen in grid["generators"]:
            missing = REQUIRED_GEN_FIELDS - set(gen.keys())
            assert not missing, f"Generator '{gen.get('name', '?')}' missing: {missing}"

    def test_loads_have_required_fields(self, grid):
        """Every load has all required fields."""
        for load in grid["loads"]:
            missing = REQUIRED_LOAD_FIELDS - set(load.keys())
            assert not missing, f"Load '{load.get('name', '?')}' missing: {missing}"

    def test_bus_references_valid(self, grid):
        """All line/gen/load references point to valid bus IDs."""
        check_bus_references_valid(grid["buses"], grid["lines"],
                                    grid["generators"], grid["loads"])

    def test_all_buses_330kv(self, grid):
        """All buses should have v_nom == 330.0."""
        for bus in grid["buses"]:
            assert bus["v_nom"] == 330.0, \
                f"Bus {bus['id']} ({bus['name']}): expected 330 kV, got {bus['v_nom']}"

    def test_positive_reactance(self, grid):
        """All lines should have positive reactance."""
        for line in grid["lines"]:
            assert line["x"] > 0, f"Line {line['id']} has non-positive x: {line['x']}"

    def test_positive_rate(self, grid):
        """All lines should have positive thermal rating."""
        for line in grid["lines"]:
            assert line["rate"] > 0, f"Line {line['id']} has non-positive rate: {line['rate']}"

    def test_non_negative_resistance(self, grid):
        """All lines should have non-negative resistance."""
        for line in grid["lines"]:
            assert line["r"] >= 0, f"Line {line['id']} has negative r: {line['r']}"

    def test_positive_generation_power(self, grid):
        """All generators should have positive p_mw."""
        for gen in grid["generators"]:
            assert gen["p_mw"] > 0, f"Generator '{gen['name']}' has non-positive p_mw"

    def test_positive_load_power(self, grid):
        """All loads should have positive p_mw."""
        for load in grid["loads"]:
            assert load["p_mw"] > 0, f"Load '{load['name']}' has non-positive p_mw"

    def test_no_self_loops(self, grid):
        """No line should connect a bus to itself."""
        for line in grid["lines"]:
            assert line["from_bus"] != line["to_bus"], \
                f"Line {line['id']} is a self-loop: {line['from_bus']} → {line['to_bus']}"

    def test_bus_positions_positive(self, grid):
        """Bus x/y positions should be non-negative (canvas coordinates)."""
        for bus in grid["buses"]:
            assert bus["x"] >= 0, f"Bus {bus['id']} has negative x: {bus['x']}"
            assert bus["y"] >= 0, f"Bus {bus['id']} has negative y: {bus['y']}"


# ─── 28-Bus Grid Tests ─────────────────────────────────────

class TestLargeUkraineGrid:
    """Test get_large_ukraine_grid() structural integrity."""

    @pytest.fixture
    def grid(self):
        return get_large_ukraine_grid()

    def test_returns_dict_with_required_keys(self, grid):
        """Grid dict has all required top-level keys."""
        check_grid_structure(grid)

    def test_name(self, grid):
        """Grid name should contain '28-bus' and 'Ukraine'."""
        assert "28" in grid["name"]
        assert "Ukraine" in grid["name"]

    def test_bus_count(self, grid):
        """Should have exactly 28 buses (18 original + 10 new)."""
        assert len(grid["buses"]) == 28

    def test_line_count(self, grid):
        """Should have exactly 38 lines (25 original + 13 new)."""
        assert len(grid["lines"]) == 38

    def test_generator_count(self, grid):
        """Should have 10 generators (8 original + 2 new)."""
        assert len(grid["generators"]) == 10

    def test_load_count(self, grid):
        """Should have 16 loads (8 original + 8 new)."""
        assert len(grid["loads"]) == 16

    def test_contains_18bus_buses(self, grid):
        """28-bus grid should contain all 18-bus buses."""
        grid18 = get_ukraine_330kv_grid()
        bus18_names = {b["name"] for b in grid18["buses"]}
        bus28_names = {b["name"] for b in grid["buses"]}
        assert bus18_names.issubset(bus28_names), \
            "28-bus grid missing some 18-bus buses"

    def test_contains_18bus_lines(self, grid):
        """28-bus grid should contain all 18-bus lines."""
        grid18 = get_ukraine_330kv_grid()
        line18_names = {ln["name"] for ln in grid18["lines"]}
        line28_names = {ln["name"] for ln in grid["lines"]}
        assert line18_names.issubset(line28_names), \
            "28-bus grid missing some 18-bus lines"

    def test_bus_ids_unique(self, grid):
        """All bus IDs are unique."""
        check_bus_ids_unique(grid["buses"])

    def test_line_ids_unique(self, grid):
        """All line IDs are unique."""
        check_line_ids_unique(grid["lines"])

    def test_bus_references_valid(self, grid):
        """All line/gen/load references point to valid bus IDs."""
        check_bus_references_valid(grid["buses"], grid["lines"],
                                    grid["generators"], grid["loads"])

    def test_new_buses_have_220kv(self, grid):
        """New (extended) buses should have v_nom == 220.0."""
        grid18 = get_ukraine_330kv_grid()
        bus18_ids = {b["id"] for b in grid18["buses"]}
        for bus in grid["buses"]:
            if bus["id"] not in bus18_ids:
                assert bus["v_nom"] == 220.0, \
                    f"Extended bus {bus['id']} ({bus['name']}): expected 220 kV"

    def test_no_self_loops(self, grid):
        """No line should connect a bus to itself."""
        for line in grid["lines"]:
            assert line["from_bus"] != line["to_bus"], \
                f"Line {line['id']} is a self-loop"

    def test_positive_reactance(self, grid):
        """All lines should have positive reactance."""
        for line in grid["lines"]:
            assert line["x"] > 0, f"Line {line['id']} has non-positive x"


# ─── Sample Grid (Deprecated) Tests ─────────────────────────

class TestSampleUkraineGrid:
    """Test get_sample_ukraine_grid() — deprecated wrapper."""

    def test_returns_same_as_330kv(self):
        """get_sample_ukraine_grid should return same as get_ukraine_330kv_grid."""
        sample = get_sample_ukraine_grid()
        ref = get_ukraine_330kv_grid()
        assert sample == ref, "Sample grid differs from 330 kV grid"

    def test_has_18_buses(self):
        """Sample grid should have 18 buses."""
        grid = get_sample_ukraine_grid()
        assert len(grid["buses"]) == 18

    def test_has_25_lines(self):
        """Sample grid should have 25 lines."""
        grid = get_sample_ukraine_grid()
        assert len(grid["lines"]) == 25
