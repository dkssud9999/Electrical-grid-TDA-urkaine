"""Tests for ptdf_calculator.py — PTDF, LODF, Effective Resistance."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from electrical_distance.ptdf_calculator import (
    build_incidence_matrix,
    build_b_prime_matrix,
    compute_ptdf,
    compute_lodf,
    compute_effective_resistance_matrix,
    compute_ptdf_vector_distance,
    compute_bus_lodf_sensitivity,
)


class TestIncidenceMatrix:
    """Test build_incidence_matrix."""

    def test_3bus_3lines(self):
        """3-bus system with 3 lines: incidence matrix shape."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        C = build_incidence_matrix(3, pairs)
        assert C.shape == (3, 3), f"Expected (3,3), got {C.shape}"

        # Row sums should be 0 (each line has +1 and -1)
        np.testing.assert_array_almost_equal(C.sum(axis=1), np.zeros(3))

    def test_single_line(self):
        """Single line between two buses."""
        C = build_incidence_matrix(2, [(0, 1)])
        assert C.shape == (1, 2)
        assert C[0, 0] == 1.0
        assert C[0, 1] == -1.0


class TestBPrimeMatrix:
    """Test build_b_prime_matrix."""

    def test_3bus_reduced_shape(self):
        """Reduced B' should be (n_bus - 1) × (n_bus - 1)."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        B = build_b_prime_matrix(3, pairs, susc, slack_bus=0)
        assert B.shape == (2, 2), f"Expected (2,2), got {B.shape}"


class TestPTDF:
    """Test compute_ptdf."""

    def test_3bus_shape(self):
        """PTDF shape: (n_line, n_bus)."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        assert PTDF.shape == (3, 3), f"Expected (3,3), got {PTDF.shape}"

    def test_slack_bus_column_zero(self):
        """Slack bus column should be all zeros."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        np.testing.assert_array_almost_equal(PTDF[:, 0], np.zeros(3))

    def test_line_flow_conservation(self):
        """For a balanced injection, PTDF row sums to 0 (each line's flow change).
        Actually, PTDF row sums are not necessarily 0 — but the slack bus column is 0.
        """
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        # Slack column = 0
        assert np.allclose(PTDF[:, 0], 0.0)

    def test_5bus_shape(self):
        """5-bus system PTDF shape."""
        pairs = [(0, 1), (1, 2), (0, 3), (3, 4), (1, 3), (2, 4)]
        susc = [10.0, 10.0, 6.667, 6.667, 8.333, 8.333]
        PTDF = compute_ptdf(5, pairs, susc, slack_bus=0)
        assert PTDF.shape == (6, 5)
        np.testing.assert_array_almost_equal(PTDF[:, 0], np.zeros(6))


class TestLODF:
    """Test compute_lodf."""

    def test_3bus_shape(self):
        """LODF shape: (n_line, n_line)."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        assert LODF.shape == (3, 3)

    def test_diagonal_negative_one(self):
        """Diagonal entries of LODF should be -1 (line cannot monitor itself)."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        np.testing.assert_array_almost_equal(np.diag(LODF), np.full(3, -1.0))


class TestEffectiveResistance:
    """Test compute_effective_resistance_matrix."""

    def test_3bus_symmetric(self):
        """Effective resistance matrix should be symmetric."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        R = compute_effective_resistance_matrix(3, pairs, susc)
        assert R.shape == (3, 3)
        np.testing.assert_array_almost_equal(R, R.T)

    def test_diagonal_zero(self):
        """Diagonal of effective resistance matrix should be 0."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        R = compute_effective_resistance_matrix(3, pairs, susc)
        np.testing.assert_array_almost_equal(np.diag(R), np.zeros(3))


class TestPTDFVectorDistance:
    """Test compute_ptdf_vector_distance."""

    def test_3bus_symmetric(self):
        """Distance matrix should be symmetric."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        D = compute_ptdf_vector_distance(PTDF, p_norm=2.0)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)

    def test_diagonal_zero(self):
        """Diagonal should be 0."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        D = compute_ptdf_vector_distance(PTDF, p_norm=2.0)
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(3))


class TestBusLODFSensitivity:
    """Test compute_bus_lodf_sensitivity."""

    def test_3bus_symmetric(self):
        """Sensitivity distance matrix should be symmetric."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        D = compute_bus_lodf_sensitivity(PTDF, LODF, pairs)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_disconnected_grid(self):
        """Disconnected grid should raise error (singular B')."""
        pairs = [(0, 1)]  # Bus 2 is isolated
        susc = [10.0]
        with pytest.raises(ValueError, match="near-singular"):
            compute_ptdf(3, pairs, susc, slack_bus=0)

    def test_single_line_system(self):
        """Single line, 2-bus system."""
        pairs = [(0, 1)]
        susc = [10.0]
        PTDF = compute_ptdf(2, pairs, susc, slack_bus=0)
        assert PTDF.shape == (1, 2)
        assert PTDF[0, 0] == 0.0  # slack column

    def test_effective_resistance_single_line(self):
        """Single line effective resistance."""
        pairs = [(0, 1)]
        susc = [10.0]  # b = 10, so R_eff(0,1) = 1/b = 0.1
        R = compute_effective_resistance_matrix(2, pairs, susc)
        assert R.shape == (2, 2)
        assert R[0, 1] == pytest.approx(0.1, rel=1e-10)
        assert R[1, 0] == pytest.approx(0.1, rel=1e-10)

    def test_ptdf_l1_norm(self):
        """Test PTDF distance with L1 norm."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=0)
        D_l1 = compute_ptdf_vector_distance(PTDF, p_norm=1.0)
        D_l2 = compute_ptdf_vector_distance(PTDF, p_norm=2.0)
        assert D_l1.shape == (3, 3)
        # L1 norm should be >= L2 norm for same vectors
        assert np.all(D_l1 >= D_l2 - 1e-10), "L1 norm should be >= L2 norm"

    def test_lodf_bridge_line_no_nan(self):
        """Bridge/leaf lines should not produce NaN in LODF.

        A leaf line (connecting a degree-1 bus) has a zero denominator
        in the LODF formula because its outage would island that bus.
        The fix sets such entries to 0 instead of NaN.
        """
        pairs = [(0, 1), (0, 2), (0, 3)]
        susc = [10.0, 10.0, 10.0]
        PTDF = compute_ptdf(4, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)

        # All three lines are leaf lines (buses 1,2,3 are degree-1)
        assert not np.any(np.isnan(LODF)), "LODF should not contain NaN"
        assert not np.any(np.isinf(LODF)), "LODF should not contain Inf"

        # Off-diagonal entries for bridge lines should be 0
        for k in range(3):
            col = np.delete(LODF[:, k], k)
            assert np.all(np.abs(col) < 1e-12), (
                f"Bridge line {k} LODF off-diagonal should be ~0, got {col}"
            )

        # Diagonal should be -1
        np.testing.assert_array_almost_equal(np.diag(LODF), np.full(3, -1.0))

    def test_bus_lodf_sensitivity_no_nan_with_bridge(self):
        """Bus LODF sensitivity should produce valid distances even with bridge lines."""
        pairs = [(0, 1), (0, 2), (0, 3)]
        susc = [10.0, 10.0, 10.0]
        PTDF = compute_ptdf(4, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        D = compute_bus_lodf_sensitivity(PTDF, LODF, pairs)

        assert D.shape == (4, 4)
        assert not np.any(np.isnan(D)), "Distance matrix should not contain NaN"
        assert not np.any(np.isinf(D)), "Distance matrix should not contain Inf"
        np.testing.assert_array_almost_equal(D, D.T, err_msg="Distance matrix must be symmetric")
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(4),
                                              err_msg="Diagonal must be zero")

    # ─── New edge case tests ─────────────────────────────────

    def test_incidence_matrix_no_lines(self):
        """build_incidence_matrix with no lines should return empty (0, n_bus)."""
        C = build_incidence_matrix(3, [])
        assert C.shape == (0, 3), f"Expected (0,3), got {C.shape}"

    def test_incidence_matrix_invalid_bus_id(self):
        """build_incidence_matrix with out-of-range bus ID should raise IndexError."""
        with pytest.raises(IndexError):
            build_incidence_matrix(3, [(0, 5)])  # Bus 5 is out of range for n_bus=3

    def test_ptdf_different_slack_bus(self):
        """PTDF with slack_bus=1 should have column 1 all zeros."""
        pairs = [(0, 1), (1, 2), (0, 2)]
        susc = [10.0, 6.667, 5.0]
        PTDF = compute_ptdf(3, pairs, susc, slack_bus=1)
        assert PTDF.shape == (3, 3)
        np.testing.assert_array_almost_equal(PTDF[:, 1], np.zeros(3),
                                              err_msg="Slack bus column should be zero")

    def test_ptdf_zero_susceptances(self):
            """All-zero susceptances (infinite reactance) make B' singular.
            Should raise ValueError (same as disconnected grid)."""
            pairs = [(0, 1), (1, 2)]
            susc = [0.0, 0.0]
            with pytest.raises(ValueError, match="near-singular"):
                compute_ptdf(3, pairs, susc, slack_bus=0)

    def test_lodf_2bus_system(self):
        """LODF on 2-bus single-line system should be [[-1]]."""
        pairs = [(0, 1)]
        susc = [10.0]
        PTDF = compute_ptdf(2, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        assert LODF.shape == (1, 1)
        assert LODF[0, 0] == pytest.approx(-1.0)

    def test_lodf_no_lines(self):
        """compute_lodf with no lines should return empty matrix."""
        PTDF = np.zeros((0, 3))
        LODF = compute_lodf(PTDF, [])
        assert LODF.shape == (0, 0)

    def test_effective_resistance_disconnected(self):
            """Effective resistance with disconnected bus should produce
            a finite symmetric distance matrix (Laplacian pseudoinverse
            handles disconnected graphs)."""
            pairs = [(0, 1)]
            susc = [10.0]
            R = compute_effective_resistance_matrix(3, pairs, susc)
            assert R.shape == (3, 3)
            np.testing.assert_array_almost_equal(R, R.T, err_msg="Must be symmetric")
            np.testing.assert_array_almost_equal(np.diag(R), np.zeros(3),
                                                  err_msg="Diagonal must be zero")
            assert not np.any(np.isnan(R)), "No NaN allowed"
            assert not np.any(np.isinf(R)), "No Inf allowed"

    def test_ptdf_vector_distance_5bus(self):
        """PTDF vector distance on 5-bus system should be symmetric with zero diagonal."""
        pairs = [(0, 1), (1, 2), (0, 3), (3, 4), (1, 3), (2, 4)]
        susc = [10.0, 10.0, 6.667, 6.667, 8.333, 8.333]
        PTDF = compute_ptdf(5, pairs, susc, slack_bus=0)
        D = compute_ptdf_vector_distance(PTDF, p_norm=2.0)
        assert D.shape == (5, 5)
        np.testing.assert_array_almost_equal(D, D.T, err_msg="Distance must be symmetric")
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(5),
                                              err_msg="Diagonal must be zero")
        # All distances should be non-negative
        assert np.all(D >= -1e-12), "Distances must be non-negative"

    def test_bus_lodf_sensitivity_5bus(self):
        """Bus LODF sensitivity on 5-bus system."""
        pairs = [(0, 1), (1, 2), (0, 3), (3, 4), (1, 3), (2, 4)]
        susc = [10.0, 10.0, 6.667, 6.667, 8.333, 8.333]
        PTDF = compute_ptdf(5, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        D = compute_bus_lodf_sensitivity(PTDF, LODF, pairs)
        assert D.shape == (5, 5)
        np.testing.assert_array_almost_equal(D, D.T, err_msg="Distance must be symmetric")
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(5),
                                              err_msg="Diagonal must be zero")
        assert not np.any(np.isnan(D)), "No NaN allowed"
        assert not np.any(np.isinf(D)), "No Inf allowed"

    def test_effective_resistance_5bus(self):
        """Effective resistance on 5-bus meshed system."""
        pairs = [(0, 1), (1, 2), (0, 3), (3, 4), (1, 3), (2, 4)]
        susc = [10.0, 10.0, 6.667, 6.667, 8.333, 8.333]
        R = compute_effective_resistance_matrix(5, pairs, susc)
        assert R.shape == (5, 5)
        np.testing.assert_array_almost_equal(R, R.T, err_msg="Must be symmetric")
        np.testing.assert_array_almost_equal(np.diag(R), np.zeros(5),
                                              err_msg="Diagonal must be zero")
        # All entries should be non-negative
        assert np.all(R >= -1e-12), "Effective resistance must be non-negative"

    def test_parallel_lines(self):
        """Two parallel lines between same buses should produce valid PTDF/LODF."""
        pairs = [(0, 1), (0, 1)]  # Two lines between bus 0 and 1
        susc = [10.0, 20.0]
        PTDF = compute_ptdf(2, pairs, susc, slack_bus=0)
        assert PTDF.shape == (2, 2)
        LODF = compute_lodf(PTDF, pairs)
        assert LODF.shape == (2, 2)
        # Diagonal should be -1
        np.testing.assert_array_almost_equal(np.diag(LODF), np.full(2, -1.0))
        # No NaN
        assert not np.any(np.isnan(LODF))
        assert not np.any(np.isinf(LODF))

    def test_build_b_prime_single_bus(self):
        """build_b_prime_matrix with single bus should produce (0,0) matrix."""
        B = build_b_prime_matrix(1, [], [], slack_bus=0)
        assert B.shape == (0, 0)

    def test_ptdf_star_topology(self):
            """Star topology with center as slack: each leaf's PTDF profile
            has -1 on its own connecting line and 0 elsewhere.
            All leaf profiles should have the same L2 norm."""
            pairs = [(0, 1), (0, 2), (0, 3)]
            susc = [10.0, 10.0, 10.0]
            PTDF = compute_ptdf(4, pairs, susc, slack_bus=0)
            # Slack column (bus 0) should be zero
            np.testing.assert_array_almost_equal(PTDF[:, 0], np.zeros(3))
            # Each leaf bus has -1 on its own line
            assert PTDF[0, 1] == pytest.approx(-1.0)
            assert PTDF[1, 2] == pytest.approx(-1.0)
            assert PTDF[2, 3] == pytest.approx(-1.0)
            # L2 norm of each leaf's PTDF profile should be identical (sqrt(1) = 1.0)
            norms = [np.linalg.norm(PTDF[:, i]) for i in range(1, 4)]
            assert np.allclose(norms, norms[0])

    def test_lodf_parallel_lines_outage(self):
        """With two parallel lines between same buses, outage of one shifts
        flow entirely to the other (LODF ≈ 1.0 for the surviving line)."""
        pairs = [(0, 1), (0, 1)]  # Two parallel lines
        susc = [10.0, 10.0]
        PTDF = compute_ptdf(2, pairs, susc, slack_bus=0)
        LODF = compute_lodf(PTDF, pairs)
        # LODF[1, 0] = how much of line 0's flow shifts to line 1 when line 0 fails
        # For identical parallel lines, this should be 1.0
        assert LODF[1, 0] == pytest.approx(1.0, abs=1e-10)
        assert LODF[0, 1] == pytest.approx(1.0, abs=1e-10)
