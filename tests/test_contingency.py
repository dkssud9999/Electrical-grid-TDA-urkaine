"""
Tests for AC power flow solver and N-1 contingency analysis.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from power_grid.ac_power_flow import ACPowerFlow
from power_grid.contingency import (
    N1ContingencyAnalyzer,
    get_cycle_edges_from_vr,
    compute_alignment_score,
)
from power_grid.importer import get_test_grid_3bus, get_test_grid_5bus


# ─── AC Power Flow Tests ────────────────────────────────────

class TestACPowerFlow:
    """Test AC Newton-Raphson power flow solver."""

    def test_3bus_converges(self):
        """3-bus system should converge within reasonable iterations."""
        grid = get_test_grid_3bus()
        bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid["lines"]]
        r_list = [l["r"] for l in grid["lines"]]
        x_list = [l["x"] for l in grid["lines"]]

        solver = ACPowerFlow(len(grid["buses"]), bus_pairs, r_list, x_list)
        p_inj = np.zeros(len(grid["buses"]))
        for g in grid["generators"]:
            p_inj[g["bus"]] += g["p_mw"]
        for ld in grid["loads"]:
            p_inj[ld["bus"]] -= ld["p_mw"]

        result = solver.run_power_flow(
            p_inj, slack_bus=0, pv_buses=[1],
        )
        assert result["converged"], (
            f"ACPF did not converge (iter={result['iterations']}, "
            f"mismatch={result['mismatch']:.2e})"
        )
        assert result["iterations"] < 15
        assert result["V"].shape == (3,)
        assert result["theta"].shape == (3,)
        assert abs(result["theta"][0]) < 1e-10  # slack bus theta = 0
        assert np.all(result["V"] > 0.5)

    def test_5bus_converges(self):
        """5-bus mesh system should converge."""
        grid = get_test_grid_5bus()
        bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid["lines"]]
        r_list = [l["r"] for l in grid["lines"]]
        x_list = [l["x"] for l in grid["lines"]]

        solver = ACPowerFlow(len(grid["buses"]), bus_pairs, r_list, x_list)
        p_inj = np.zeros(len(grid["buses"]))
        for g in grid["generators"]:
            p_inj[g["bus"]] += g["p_mw"]
        for ld in grid["loads"]:
            p_inj[ld["bus"]] -= ld["p_mw"]

        result = solver.run_power_flow(
            p_inj, slack_bus=0,
        )
        assert result["converged"]
        assert result["iterations"] < 20
        assert result["branch_flows"].shape == (6,)

    def test_power_balance(self):
        """Total generation should approximately equal total load."""
        grid = get_test_grid_3bus()
        bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid["lines"]]
        r_list = [l["r"] for l in grid["lines"]]
        x_list = [l["x"] for l in grid["lines"]]

        solver = ACPowerFlow(len(grid["buses"]), bus_pairs, r_list, x_list)
        p_inj = np.zeros(len(grid["buses"]))
        for g in grid["generators"]:
            p_inj[g["bus"]] += g["p_mw"]
        for ld in grid["loads"]:
            p_inj[ld["bus"]] -= ld["p_mw"]

        solver.run_power_flow(p_inj, slack_bus=0)

        total_gen = sum(g["p_mw"] for g in grid["generators"])
        total_load = sum(ld["p_mw"] for ld in grid["loads"])
        assert abs(total_gen - total_load) < 50

    def test_no_pv_buses(self):
        """Should handle all-PQ case."""
        grid = get_test_grid_3bus()
        bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid["lines"]]
        r_list = [l["r"] for l in grid["lines"]]
        x_list = [l["x"] for l in grid["lines"]]

        solver = ACPowerFlow(len(grid["buses"]), bus_pairs, r_list, x_list)
        p_inj = np.array([100.0, 0.0, -100.0])

        result = solver.run_power_flow(
            p_inj, slack_bus=0, pv_buses=[],
        )
        assert result["converged"]

    def test_branch_flows_shape(self):
        """Branch flows should match number of lines."""
        grid = get_test_grid_3bus()
        bus_pairs = [(l["from_bus"], l["to_bus"]) for l in grid["lines"]]
        r_list = [l["r"] for l in grid["lines"]]
        x_list = [l["x"] for l in grid["lines"]]

        solver = ACPowerFlow(len(grid["buses"]), bus_pairs, r_list, x_list)
        p_inj = np.zeros(len(grid["buses"]))
        for g in grid["generators"]:
            p_inj[g["bus"]] += g["p_mw"]
        for ld in grid["loads"]:
            p_inj[ld["bus"]] -= ld["p_mw"]

        result = solver.run_power_flow(p_inj, slack_bus=0)
        assert result["branch_flows"].shape == (3,)


# ─── N-1 Contingency Tests ──────────────────────────────────

class TestN1ContingencyAnalyzer:
    """Test N-1 contingency analysis."""

    def test_3bus_analysis_runs(self):
        """3-bus N-1 analysis should complete without error."""
        grid = get_test_grid_3bus()
        analyzer = N1ContingencyAnalyzer(grid)
        result = analyzer.analyze()

        assert result["n_bus"] == 3
        assert result["n_line"] == 3
        assert result["total_edges"] == 3
        assert isinstance(result["vulnerable_edge_ids"], set)
        assert isinstance(result["vulnerable_edges"], list)
        assert 0 <= result["vulnerability_ratio"] <= 1.0

    def test_5bus_analysis_runs(self):
        """5-bus N-1 analysis should complete."""
        grid = get_test_grid_5bus()
        analyzer = N1ContingencyAnalyzer(grid)
        result = analyzer.analyze()

        assert result["n_bus"] == 5
        assert result["n_line"] == 6
        assert result["total_edges"] == 6

    def test_violation_details_structure(self):
        """Violation details should have correct structure."""
        grid = get_test_grid_3bus()
        analyzer = N1ContingencyAnalyzer(grid)
        result = analyzer.analyze()

        for line_id, details in result["violation_details"].items():
            assert "line_name" in details
            assert "violations" in details
            assert isinstance(details["violations"], list)
            assert "converged" in details

    def test_base_case_present(self):
        """Base case power flow results should be included."""
        grid = get_test_grid_3bus()
        analyzer = N1ContingencyAnalyzer(grid)
        result = analyzer.analyze()

        assert "base_case" in result
        assert "converged" in result["base_case"]
        assert "V" in result["base_case"]
        assert "theta" in result["base_case"]

    def test_connectivity_check(self):
        """Check connectivity detection works for 3-bus triangle."""
        grid = get_test_grid_3bus()
        analyzer = N1ContingencyAnalyzer(grid)

        for line_idx in range(3):
            is_connected, _ = analyzer._check_connectivity(line_idx)
            assert is_connected, (
                f"Line {line_idx} removal should not island 3-bus triangle"
            )

    def test_3bus_vulnerability_reasonable(self):
        """3-bus system vulnerability should be reasonable."""
        grid = get_test_grid_3bus()
        analyzer = N1ContingencyAnalyzer(grid, overload_threshold=1.0)
        result = analyzer.analyze()

        n_vuln = result["n_vulnerable"]
        assert 0 <= n_vuln <= 3
        assert result["vulnerability_ratio"] == n_vuln / 3


# ─── Cycle Edge Extraction Tests ─────────────────────────────

class TestGetCycleEdgesFromVR:
    """Test cycle edge extraction from VR persistence."""

    def test_3bus_triangle(self):
        """3-bus triangle should have cycle edges."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        bus_pairs = [(0, 1), (1, 2), (0, 2)]
        cycle_edges = get_cycle_edges_from_vr(D, bus_pairs)
        assert len(cycle_edges) > 0

    def test_empty_for_tree(self):
        """A tree (no cycles) should have no cycle edges."""
        # 4 points in a line that never form a triangle:
        #   0-1-2-3 path: D[0,2]=2, D[1,3]=2, D[0,3]=3
        # At threshold 1: edges 0-1, 1-2, 2-3 (path graph, no cycles)
        # At threshold 2: edges 0-2, 1-3 added (still a path, no cycles)
        D = np.array([
            [0, 1, 2, 3],
            [1, 0, 1, 2],
            [2, 1, 0, 1],
            [3, 2, 1, 0],
        ])
        bus_pairs = [(0, 1), (1, 2), (2, 3)]
        cycle_edges = get_cycle_edges_from_vr(D, bus_pairs)
        assert len(cycle_edges) == 0

    def test_4bus_square(self):
        """4-bus square should have cycle edges."""
        D = np.array([
            [0, 1, np.sqrt(2), 1],
            [1, 0, 1, np.sqrt(2)],
            [np.sqrt(2), 1, 0, 1],
            [1, np.sqrt(2), 1, 0],
        ])
        bus_pairs = [(0, 1), (1, 2), (2, 3), (0, 3)]
        cycle_edges = get_cycle_edges_from_vr(D, bus_pairs)
        assert len(cycle_edges) >= 4


# ─── Alignment Score Tests ──────────────────────────────────

class TestComputeAlignmentScore:
    """Test alignment score computation."""

    def test_perfect_match(self):
        """Perfect match should give alignment = intersection/total."""
        result = compute_alignment_score(
            vulnerable_edges={0, 1},
            cycle_edge_ids={0, 1},
            total_edges=4,
        )
        assert result["alignment_score"] == 2 / 4
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["true_positives"] == 2
        assert result["false_positives"] == 0
        assert result["false_negatives"] == 0

    def test_no_overlap(self):
        """No overlap should give alignment = 0."""
        result = compute_alignment_score(
            vulnerable_edges={0, 1},
            cycle_edge_ids={2, 3},
            total_edges=4,
        )
        assert result["alignment_score"] == 0.0
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0

    def test_partial_overlap(self):
        """Partial overlap should give intermediate scores."""
        result = compute_alignment_score(
            vulnerable_edges={0, 1, 2},
            cycle_edge_ids={0, 3},
            total_edges=5,
        )
        assert result["true_positives"] == 1
        assert result["false_positives"] == 1
        assert result["false_negatives"] == 2
        assert result["true_negatives"] == 1
        assert result["alignment_score"] == 1 / 5
        assert result["precision"] == 1 / 2
        assert result["recall"] == 1 / 3
        assert abs(result["recall"] - 0.333) < 0.01

    def test_empty_sets(self):
        """Empty sets should give zero scores (no division by zero)."""
        result = compute_alignment_score(
            vulnerable_edges=set(),
            cycle_edge_ids=set(),
            total_edges=5,
        )
        assert result["alignment_score"] == 0.0
        assert result["precision"] == 0.0
        assert result["recall"] == 0.0
        assert result["specificity"] == 1.0


# ─── Integration Tests ──────────────────────────────────────

class TestVulnerabilityIntegration:
    """Integration tests for vulnerability analysis pipeline."""

    def test_analyze_grid_vulnerability(self):
        """analyze_grid_vulnerability convenience function."""
        from power_grid.contingency import analyze_grid_vulnerability
        grid = get_test_grid_3bus()
        result = analyze_grid_vulnerability(grid)
        assert result["n_bus"] == 3
        assert result["n_line"] == 3

    def test_compare_with_homology_runs(self):
        """compare_with_homology should complete on 3-bus system."""
        from tda.vulnerability import compare_with_homology
        grid = get_test_grid_3bus()

        D = np.array([
            [0, 0.5, 0.5],
            [0.5, 0, 0.5],
            [0.5, 0.5, 0],
        ])

        result = compare_with_homology(grid, D)
        assert result["n_bus"] == 3
        assert result["n_line"] == 3
        assert "alignment_score" in result
        assert "vulnerable_edge_ids" in result
        assert "cycle_edge_ids" in result
        assert "homology" in result
        assert "n1_analysis" in result

    def test_compare_metrics_vulnerability_runs(self):
        """compare_metrics_vulnerability should handle multiple metrics."""
        from tda.vulnerability import compare_metrics_vulnerability
        grid = get_test_grid_3bus()

        D1 = np.array([
            [0, 0.5, 0.5],
            [0.5, 0, 0.5],
            [0.5, 0.5, 0],
        ])
        D2 = np.array([
            [0, 0.3, 0.7],
            [0.3, 0, 0.4],
            [0.7, 0.4, 0],
        ])

        result = compare_metrics_vulnerability(
            grid, {"MetricA": D1, "MetricB": D2},
        )
        assert result["n_bus"] == 3
        assert result["n_line"] == 3
        assert len(result["metrics"]) == 2
        assert "MetricA" in result["results"]
        assert "MetricB" in result["results"]

    def test_get_cycle_edges(self):
        """get_cycle_edges should work with bus_pairs."""
        from tda.vulnerability import get_cycle_edges
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        bus_pairs = [(0, 1), (1, 2), (0, 2)]
        edges = get_cycle_edges(D, bus_pairs)
        assert len(edges) > 0
        for f, t in edges:
            assert (f, t) in bus_pairs or (t, f) in bus_pairs

    def test_get_cycle_edge_ids(self):
        """get_cycle_edge_ids should return line IDs."""
        from tda.vulnerability import get_cycle_edge_ids
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        bus_pairs = [(0, 1), (1, 2), (0, 2)]
        line_id_map = {
            (0, 1): 0, (1, 0): 0,
            (1, 2): 1, (2, 1): 1,
            (0, 2): 2, (2, 0): 2,
        }
        ids = get_cycle_edge_ids(D, bus_pairs, line_id_map)
        assert len(ids) > 0
        assert all(isinstance(i, int) for i in ids)
