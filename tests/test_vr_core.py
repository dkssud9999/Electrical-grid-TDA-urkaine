"""Tests for vr_core.py — Vietoris-Rips complex persistence."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from tda.vr_core import VRComplex


class TestVRComplexInitialization:
    """Test VRComplex init and basic properties."""

    def test_triangle(self):
        """Equilateral triangle: all distances = 1."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        assert vr.n == 3
        assert vr.max_distance == pytest.approx(1.0)
        assert len(vr.unique_thresholds) == 1

    def test_asymmetric_matrix_raises(self):
        """Non-symmetric distance matrix should raise."""
        D = np.array([
            [0, 1, 2],
            [1, 0, 1],
            [2, 1, 0],
        ])
        vr = VRComplex(D)
        assert vr.n == 3

        D_bad = np.array([
            [0, 1, 3],
            [1, 0, 1],
            [2, 1, 0],
        ])
        with pytest.raises(AssertionError):
            VRComplex(D_bad)


class TestPersistencePairs:
    """Test persistence_pairs output."""

    def test_two_points(self):
        """Two points at distance 1: H0 should have (0, inf) and (0, 1)."""
        D = np.array([
            [0, 1],
            [1, 0],
        ])
        vr = VRComplex(D)
        h0, h1 = vr.persistence_pairs()

        assert len(h0) == 2
        assert len(h1) == 0

        births = [b for b, d in h0]
        deaths = [d for b, d in h0]
        assert 0.0 in births
        assert 1.0 in deaths
        assert any(d >= 1.5 for b, d in h0)

    def test_triangle_h1(self):
        """Equilateral triangle: H1 should have one cycle at d=1."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        h0, h1 = vr.persistence_pairs()

        assert len(h0) == 3
        assert len(h1) == 1
        b, d = h1[0]
        assert b == pytest.approx(1.0)
        assert d > 1.0

    def test_square_diagonal(self):
        """Square with diagonals: H1 born at 1.0, dies at max_dist*1.5."""
        sqrt2 = np.sqrt(2)
        D = np.array([
            [0, 1, sqrt2, 1],
            [1, 0, 1, sqrt2],
            [sqrt2, 1, 0, 1],
            [1, sqrt2, 1, 0],
        ])
        vr = VRComplex(D)
        h0, h1 = vr.persistence_pairs()

        assert len(h0) == 4
        assert len(h1) == 3
        has_cycle_born_at_1 = any(abs(b - 1.0) < 1e-6 for b, d in h1)
        assert has_cycle_born_at_1, f"No cycle born at 1.0 in {h1}"

    def test_disconnected_components(self):
        """Two clusters far apart: H1 created when clusters merge."""
        D = np.array([
            [0, 1, 10, 10],
            [1, 0, 10, 10],
            [10, 10, 0, 1],
            [10, 10, 1, 0],
        ])
        vr = VRComplex(D)
        h0, h1 = vr.persistence_pairs()

        assert len(h0) == 4
        assert len(h1) == 3
        for b, d in h1:
            assert b == pytest.approx(10.0)


class TestBettiNumbers:
    """Test betti_numbers at various thresholds."""

    def test_triangle_betti_at_0(self):
        """At alpha=0, triangle: beta0=3, beta1=0."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        b0, b1 = vr.betti_numbers(0.0)
        assert b0 == 3
        assert b1 == 0

    def test_triangle_betti_at_1(self):
        """At alpha=1, triangle: beta0=1, beta1=1."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        b0, b1 = vr.betti_numbers(1.0)
        assert b0 == 1
        assert b1 == 1

    def test_triangle_betti_large(self):
        """At large alpha: beta0=1, beta1=1 (only 1-skeleton)."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        b0, b1 = vr.betti_numbers(2.0)
        assert b0 == 1
        assert b1 == 1


class TestBettiCurves:
    """Test betti_curves output."""

    def test_triangle_curves(self):
        """Triangle Betti curves should have correct shapes."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        thr, b0v, b1v = vr.betti_curves()

        assert len(thr) == 1
        assert thr[0] == pytest.approx(1.0)
        assert b0v[0] == 1
        assert b1v[0] == 1


class TestCaching:
    """Test that persistence_pairs is cached."""

    def test_cache(self):
        """Second call should return same object."""
        D = np.array([
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ])
        vr = VRComplex(D)
        h0_1, h1_1 = vr.persistence_pairs()
        h0_2, h1_2 = vr.persistence_pairs()
        assert h0_1 is h0_2
        assert h1_1 is h1_2

